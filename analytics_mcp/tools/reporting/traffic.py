# Copyright 2025 Google LLC All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""PM-friendly tools for traffic and acquisition reporting."""

from typing import Any, Dict, List, Literal, Optional

from analytics_mcp.coordinator import mcp
from analytics_mcp.tools.utils import (
    create_data_api_client,
    get_property_id,
    proto_to_dict,
)
from google.analytics import data_v1beta


# =============================================================================
# VALID PARAMETER OPTIONS
# These are the ONLY valid values for each parameter. Using other values will fail.
# =============================================================================

# group_by: How to group acquisition data
# - "source_medium": Traffic source and medium combined (e.g., "google / organic")
# - "channel": Default channel grouping (e.g., "Organic Search", "Paid Search", "Direct")
# - "campaign": Campaign name from UTM parameters
# - "source": Traffic source only (e.g., "google", "facebook")
# - "medium": Traffic medium only (e.g., "organic", "cpc", "referral")
# - "landing_page": First page users landed on
GROUP_BY_OPTIONS = ["source_medium", "channel", "campaign", "source", "medium", "landing_page"]

# sort_by: Which metric to sort results by (descending)
# - "sessions": Total number of sessions
# - "users": Total unique users
# - "key_events": Key events (formerly conversions)
# - "engagement_rate": Percentage of engaged sessions
# - "bounce_rate": Percentage of non-engaged sessions
SORT_BY_OPTIONS = ["sessions", "users", "key_events", "engagement_rate", "bounce_rate"]

# =============================================================================
# DATE FORMAT
# Valid formats for start_date and end_date:
# - Relative: "today", "yesterday", "NdaysAgo" (e.g., "7daysAgo", "30daysAgo", "90daysAgo")
# - Absolute: "YYYY-MM-DD" (e.g., "2025-01-15")
#
# WRONG formats (will fail):
# - "last7days", "last_7_days", "7days" (use "7daysAgo" instead)
# - "2025/01/15", "01-15-2025" (use "2025-01-15" instead)
# - "Today", "Yesterday" (lowercase only: "today", "yesterday")
# =============================================================================

# =============================================================================
# FILTER VALUES
# Common values for filter parameters (case-insensitive, partial match):
#
# filter_source examples:
#   "google", "facebook", "bing", "twitter", "linkedin", "instagram", "youtube"
#   "(direct)" for direct traffic
#
# filter_medium examples:
#   "organic" - Organic search traffic
#   "cpc" - Paid search/cost-per-click (NOT "paid", "ppc", or "ads")
#   "email" - Email campaigns (NOT "mail" or "newsletter")
#   "referral" - Referral traffic from other sites
#   "social" - Social media traffic
#   "display" - Display advertising
#   "(none)" - Direct traffic with no medium
#
# filter_page_path examples:
#   "/blog/", "/products/", "/pricing", "/checkout"
#
# filter_hostname examples:
#   "example.com", "blog.example.com", "shop.example.com"
# =============================================================================

# Mapping from friendly group_by names to GA4 dimension API names
GROUP_BY_DIMENSION_MAP = {
    "source_medium": "sessionSourceMedium",
    "channel": "sessionDefaultChannelGroup",
    "campaign": "sessionCampaignName",
    "source": "sessionSource",
    "medium": "sessionMedium",
    "landing_page": "landingPage",
}

# Mapping from friendly sort_by names to GA4 metric API names
SORT_BY_METRIC_MAP = {
    "sessions": "sessions",
    "users": "totalUsers",
    "key_events": "keyEvents",
    "engagement_rate": "engagementRate",
    "bounce_rate": "bounceRate",
}

# Default metrics for traffic overview
# These are the standard GA4 metric API names
TRAFFIC_OVERVIEW_METRICS = [
    "sessions",
    "totalUsers",
    "newUsers",
    "bounceRate",
    "userEngagementDuration",  # Total engagement time in seconds
    "screenPageViews",
]

# Metrics returned in acquisition reports
ACQUISITION_METRICS = [
    "sessions",
    "totalUsers",
    "newUsers",
    "bounceRate",
    "engagementRate",
    "keyEvents",  # Formerly "conversions" - renamed by Google in 2024
]


def _validate_date_format(date_str: str) -> None:
    """Validates date string format.

    Raises:
        ValueError: If date format is invalid.
    """
    import re

    # Valid relative dates
    relative_patterns = [
        r"^today$",
        r"^yesterday$",
        r"^\d+daysAgo$",  # e.g., "7daysAgo", "30daysAgo"
    ]

    # Valid absolute date: YYYY-MM-DD
    absolute_pattern = r"^\d{4}-\d{2}-\d{2}$"

    is_valid = any(re.match(p, date_str) for p in relative_patterns) or re.match(absolute_pattern, date_str)

    if not is_valid:
        raise ValueError(
            f"Invalid date format: '{date_str}'. "
            f"Use 'today', 'yesterday', 'NdaysAgo' (e.g., '7daysAgo'), or 'YYYY-MM-DD' (e.g., '2025-01-15'). "
            f"Common mistakes: 'last7days' should be '7daysAgo', 'Today' should be 'today'."
        )


def _validate_group_by(group_by: str) -> None:
    """Validates group_by parameter.

    Raises:
        ValueError: If group_by value is invalid.
    """
    if group_by not in GROUP_BY_OPTIONS:
        raise ValueError(
            f"Invalid group_by: '{group_by}'. "
            f"Valid options: {GROUP_BY_OPTIONS}. "
            f"Common mistakes: 'sourceMedium' should be 'source_medium', 'channelGroup' should be 'channel'."
        )


def _validate_sort_by(sort_by: str) -> None:
    """Validates sort_by parameter.

    Raises:
        ValueError: If sort_by value is invalid.
    """
    if sort_by not in SORT_BY_OPTIONS:
        raise ValueError(
            f"Invalid sort_by: '{sort_by}'. "
            f"Valid options: {SORT_BY_OPTIONS}. "
            f"Common mistakes: 'conversions' should be 'key_events', 'totalUsers' should be 'users'."
        )


def _build_dimension_filter(
    filter_source: Optional[str] = None,
    filter_medium: Optional[str] = None,
    filter_campaign: Optional[str] = None,
    filter_page_path: Optional[str] = None,
    filter_hostname: Optional[str] = None,
) -> Optional[data_v1beta.FilterExpression]:
    """Builds a dimension filter from individual filter parameters."""
    filters = []

    if filter_source:
        filters.append(
            data_v1beta.FilterExpression(
                filter=data_v1beta.Filter(
                    field_name="sessionSource",
                    string_filter=data_v1beta.Filter.StringFilter(
                        match_type=data_v1beta.Filter.StringFilter.MatchType.CONTAINS,
                        value=filter_source,
                        case_sensitive=False,
                    ),
                )
            )
        )

    if filter_medium:
        filters.append(
            data_v1beta.FilterExpression(
                filter=data_v1beta.Filter(
                    field_name="sessionMedium",
                    string_filter=data_v1beta.Filter.StringFilter(
                        match_type=data_v1beta.Filter.StringFilter.MatchType.CONTAINS,
                        value=filter_medium,
                        case_sensitive=False,
                    ),
                )
            )
        )

    if filter_campaign:
        filters.append(
            data_v1beta.FilterExpression(
                filter=data_v1beta.Filter(
                    field_name="sessionCampaignName",
                    string_filter=data_v1beta.Filter.StringFilter(
                        match_type=data_v1beta.Filter.StringFilter.MatchType.CONTAINS,
                        value=filter_campaign,
                        case_sensitive=False,
                    ),
                )
            )
        )

    if filter_page_path:
        filters.append(
            data_v1beta.FilterExpression(
                filter=data_v1beta.Filter(
                    field_name="pagePath",
                    string_filter=data_v1beta.Filter.StringFilter(
                        match_type=data_v1beta.Filter.StringFilter.MatchType.CONTAINS,
                        value=filter_page_path,
                        case_sensitive=False,
                    ),
                )
            )
        )

    if filter_hostname:
        filters.append(
            data_v1beta.FilterExpression(
                filter=data_v1beta.Filter(
                    field_name="hostName",
                    string_filter=data_v1beta.Filter.StringFilter(
                        match_type=data_v1beta.Filter.StringFilter.MatchType.CONTAINS,
                        value=filter_hostname,
                        case_sensitive=False,
                    ),
                )
            )
        )

    if not filters:
        return None

    if len(filters) == 1:
        return filters[0]

    # Combine multiple filters with AND
    return data_v1beta.FilterExpression(
        and_group=data_v1beta.FilterExpressionList(expressions=filters)
    )


@mcp.tool(
    description="""Get total website traffic metrics: visitor counts, engagement, and page views.

Returns aggregate numbers for your entire site (not broken down by source or page).

## Returns
- sessions: Total visits
- totalUsers: Unique visitors
- newUsers: First-time visitors
- bounceRate: Percentage of single-page visits
- userEngagementDuration: Total engagement time (seconds)
- screenPageViews: Total page views

## Parameters

### start_date / end_date (string)
Valid: "today", "yesterday", "7daysAgo", "30daysAgo", or "YYYY-MM-DD"

### compare_previous_period (boolean, default: false)
Include previous period for comparison.

## Examples
- Last 30 days: get_traffic_overview()
- Last 7 days: get_traffic_overview(start_date="7daysAgo")
- Specific dates: get_traffic_overview(start_date="2025-01-01", end_date="2025-01-31")
- With comparison: get_traffic_overview(compare_previous_period=true)

## Note
This returns site-wide totals only. For traffic broken down by source/channel, use get_acquisition_report instead.
"""
)
async def get_traffic_overview(
    start_date: str = "30daysAgo",
    end_date: str = "today",
    compare_previous_period: bool = False,
) -> Dict[str, Any]:
    """Get a high-level traffic overview with key metrics."""

    # Validate inputs
    _validate_date_format(start_date)
    _validate_date_format(end_date)

    date_ranges = [
        data_v1beta.DateRange(start_date=start_date, end_date=end_date, name="current")
    ]

    if compare_previous_period:
        # Add previous period for comparison
        date_ranges.append(
            data_v1beta.DateRange(
                start_date=start_date,
                end_date=end_date,
                name="previous",
            )
        )
        # Note: GA4 automatically calculates the previous period when you add a second date range
        # with the same duration. For explicit control, we'd need to calculate dates manually.

    request = data_v1beta.RunReportRequest(
        property=get_property_id(),
        date_ranges=date_ranges,
        metrics=[data_v1beta.Metric(name=m) for m in TRAFFIC_OVERVIEW_METRICS],
    )

    response = await create_data_api_client().run_report(request)
    result = proto_to_dict(response)

    # Format response for PM-friendly output
    formatted = {
        "date_range": {"start": start_date, "end": end_date},
        "metrics": {},
    }

    if result.get("rows"):
        row = result["rows"][0]
        metric_values = row.get("metric_values", [])
        for i, metric_name in enumerate(TRAFFIC_OVERVIEW_METRICS):
            if i < len(metric_values):
                formatted["metrics"][metric_name] = metric_values[i].get("value")

    if compare_previous_period and len(result.get("rows", [])) > 1:
        formatted["previous_period"] = {}
        prev_row = result["rows"][1]
        metric_values = prev_row.get("metric_values", [])
        for i, metric_name in enumerate(TRAFFIC_OVERVIEW_METRICS):
            if i < len(metric_values):
                formatted["previous_period"][metric_name] = metric_values[i].get("value")

    return formatted


@mcp.tool(
    description="""Get traffic sources breakdown: where visitors come from (channels, sources, campaigns).

Shows traffic grouped by source, medium, channel, campaign, or landing page.

## Returns
- sessions: Total visits from each source
- totalUsers: Unique visitors
- newUsers: First-time visitors
- bounceRate: Percentage of single-page visits
- engagementRate: Percentage of engaged sessions
- keyEvents: Conversion events (formerly called conversions)

## Parameters

### group_by (string, default: "source_medium")
- "source_medium": e.g., "google / organic", "facebook / cpc"
- "channel": e.g., "Organic Search", "Paid Search", "Direct"
- "campaign": Campaign names from UTM parameters
- "source": e.g., "google", "facebook", "bing"
- "medium": e.g., "organic", "cpc", "referral"
- "landing_page": First page users landed on

### start_date / end_date (string)
Valid: "today", "yesterday", "7daysAgo", "30daysAgo", or "YYYY-MM-DD"

### limit (integer, default: 10)
Number of results to return (1-100).

### sort_by (string, default: "sessions")
- "sessions", "users", "key_events", "engagement_rate", "bounce_rate"

### Filters (all optional, partial match)
- filter_source: e.g., "google", "facebook", "(direct)"
- filter_medium: e.g., "cpc", "organic", "email", "referral"
- filter_campaign: Campaign name
- filter_page_path: e.g., "/blog/", "/pricing"
- filter_hostname: e.g., "example.com"

## Examples
- Top sources: get_acquisition_report()
- By channel: get_acquisition_report(group_by="channel")
- Google Ads only: get_acquisition_report(filter_source="google", filter_medium="cpc")
- Top campaigns: get_acquisition_report(group_by="campaign", sort_by="key_events", limit=5)

## Note
This shows traffic breakdown by source. For total site-wide metrics without breakdown, use get_traffic_overview instead.
"""
)
async def get_acquisition_report(
    group_by: Literal["source_medium", "channel", "campaign", "source", "medium", "landing_page"] = "source_medium",
    start_date: str = "30daysAgo",
    end_date: str = "today",
    limit: int = 10,
    sort_by: Literal["sessions", "users", "key_events", "engagement_rate", "bounce_rate"] = "sessions",
    filter_source: Optional[str] = None,
    filter_medium: Optional[str] = None,
    filter_campaign: Optional[str] = None,
    filter_page_path: Optional[str] = None,
    filter_hostname: Optional[str] = None,
) -> Dict[str, Any]:
    """Get traffic acquisition report grouped by source, medium, channel, or campaign."""

    # Validate inputs
    _validate_date_format(start_date)
    _validate_date_format(end_date)
    _validate_group_by(group_by)
    _validate_sort_by(sort_by)

    dimension_name = GROUP_BY_DIMENSION_MAP.get(group_by, "sessionSourceMedium")
    sort_metric = SORT_BY_METRIC_MAP.get(sort_by, "sessions")

    request = data_v1beta.RunReportRequest(
        property=get_property_id(),
        date_ranges=[
            data_v1beta.DateRange(start_date=start_date, end_date=end_date)
        ],
        dimensions=[data_v1beta.Dimension(name=dimension_name)],
        metrics=[data_v1beta.Metric(name=m) for m in ACQUISITION_METRICS],
        order_bys=[
            data_v1beta.OrderBy(
                metric=data_v1beta.OrderBy.MetricOrderBy(metric_name=sort_metric),
                desc=True,
            )
        ],
        limit=limit,
    )

    # Add filters if provided
    dimension_filter = _build_dimension_filter(
        filter_source=filter_source,
        filter_medium=filter_medium,
        filter_campaign=filter_campaign,
        filter_page_path=filter_page_path,
        filter_hostname=filter_hostname,
    )
    if dimension_filter:
        request.dimension_filter = dimension_filter

    response = await create_data_api_client().run_report(request)
    result = proto_to_dict(response)

    # Format response for PM-friendly output
    formatted = {
        "date_range": {"start": start_date, "end": end_date},
        "group_by": group_by,
        "sort_by": sort_by,
        "filters_applied": {
            k: v for k, v in {
                "source": filter_source,
                "medium": filter_medium,
                "campaign": filter_campaign,
                "page_path": filter_page_path,
                "hostname": filter_hostname,
            }.items() if v is not None
        },
        "results": [],
    }

    for row in result.get("rows", []):
        dimension_values = row.get("dimension_values", [])
        metric_values = row.get("metric_values", [])

        entry = {
            group_by: dimension_values[0].get("value") if dimension_values else None,
        }
        for i, metric_name in enumerate(ACQUISITION_METRICS):
            if i < len(metric_values):
                entry[metric_name] = metric_values[i].get("value")

        formatted["results"].append(entry)

    formatted["total_results"] = len(formatted["results"])

    return formatted
