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

"""PM-friendly tools for Google Ads reporting via GA4."""

from typing import Any, Dict, Literal, Optional

from analytics_mcp.coordinator import mcp
from analytics_mcp.tools.utils import (
    create_data_api_client,
    get_property_id,
    proto_to_dict,
)
from analytics_mcp.tools.reporting.acquisition import _validate_date_format
from google.analytics import data_v1beta


# =============================================================================
# GOOGLE ADS CAMPAIGN PERFORMANCE
# =============================================================================

# Metrics for Google Ads reports
ADS_METRICS = [
    "sessions",
    "totalUsers",
    "keyEvents",
    "engagementRate",
    "bounceRate",
    "userEngagementDuration",
]

# Mapping for group_by options
ADS_GROUP_BY_MAP = {
    "campaign": "sessionGoogleAdsCampaignName",
    "ad_group": "sessionGoogleAdsAdGroupName",
    "keyword": "sessionGoogleAdsQuery",
    "ad_network": "sessionGoogleAdsAdNetworkType",
}

# Mapping for sort_by options
ADS_SORT_BY_MAP = {
    "sessions": "sessions",
    "users": "totalUsers",
    "key_events": "keyEvents",
    "engagement_rate": "engagementRate",
    "bounce_rate": "bounceRate",
}


@mcp.tool(
    description="""Get Google Ads performance: campaign, ad group, and keyword metrics from GA4.

Shows how your Google Ads traffic performs in terms of engagement and conversions.

## Requirements
- Google Ads account must be linked to your GA4 property
- Data shows only Google Ads traffic (not other paid sources)

## Returns
- sessions: Visits from Google Ads
- totalUsers: Unique visitors from ads
- keyEvents: Conversions attributed to ads
- engagementRate: Percentage of engaged sessions
- bounceRate: Percentage of single-page visits
- userEngagementDuration: Engagement time (seconds)

## Parameters

### group_by (string, default: "campaign")
- "campaign": Google Ads campaign name
- "ad_group": Ad group within campaigns
- "keyword": Search queries that triggered ads
- "ad_network": Network type (Search, Display, YouTube, etc.)

### start_date / end_date (string)
Valid: "today", "yesterday", "7daysAgo", "30daysAgo", or "YYYY-MM-DD"

### limit (integer, default: 10)
Number of results to return (1-100).

### sort_by (string, default: "sessions")
- "sessions": Sort by visit count
- "users": Sort by unique visitors
- "key_events": Sort by conversions
- "engagement_rate": Sort by engagement rate
- "bounce_rate": Sort by bounce rate

### filter_campaign (string, optional)
Filter by campaign name. Partial match, case-insensitive.

## Examples
- Top campaigns: get_google_ads_performance()
- Ad groups by conversions: get_google_ads_performance(group_by="ad_group", sort_by="key_events")
- Top keywords: get_google_ads_performance(group_by="keyword", limit=20)
- Specific campaign: get_google_ads_performance(filter_campaign="Brand")

## Note
This shows GA4 engagement metrics for Google Ads traffic. For cost/CPC/impressions data, use the Google Ads API directly or check your Ads dashboard.
"""
)
async def get_google_ads_performance(
    group_by: Literal["campaign", "ad_group", "keyword", "ad_network"] = "campaign",
    start_date: str = "30daysAgo",
    end_date: str = "today",
    limit: int = 10,
    sort_by: Literal["sessions", "users", "key_events", "engagement_rate", "bounce_rate"] = "sessions",
    filter_campaign: Optional[str] = None,
) -> Dict[str, Any]:
    """Get Google Ads performance report from GA4."""

    _validate_date_format(start_date)
    _validate_date_format(end_date)

    if group_by not in ADS_GROUP_BY_MAP:
        raise ValueError(f"Invalid group_by: '{group_by}'. Valid options: {list(ADS_GROUP_BY_MAP.keys())}")

    if sort_by not in ADS_SORT_BY_MAP:
        raise ValueError(f"Invalid sort_by: '{sort_by}'. Valid options: {list(ADS_SORT_BY_MAP.keys())}")

    dimension_name = ADS_GROUP_BY_MAP[group_by]
    sort_metric = ADS_SORT_BY_MAP[sort_by]

    request = data_v1beta.RunReportRequest(
        property=get_property_id(),
        date_ranges=[
            data_v1beta.DateRange(start_date=start_date, end_date=end_date)
        ],
        dimensions=[data_v1beta.Dimension(name=dimension_name)],
        metrics=[data_v1beta.Metric(name=m) for m in ADS_METRICS],
        order_bys=[
            data_v1beta.OrderBy(
                metric=data_v1beta.OrderBy.MetricOrderBy(metric_name=sort_metric),
                desc=True,
            )
        ],
        limit=limit,
    )

    # Add campaign filter if specified
    if filter_campaign:
        request.dimension_filter = data_v1beta.FilterExpression(
            filter=data_v1beta.Filter(
                field_name="sessionGoogleAdsCampaignName",
                string_filter=data_v1beta.Filter.StringFilter(
                    match_type=data_v1beta.Filter.StringFilter.MatchType.CONTAINS,
                    value=filter_campaign,
                    case_sensitive=False,
                ),
            )
        )

    response = await create_data_api_client().run_report(request)
    result = proto_to_dict(response)

    formatted = {
        "date_range": {"start": start_date, "end": end_date},
        "group_by": group_by,
        "sort_by": sort_by,
        "filters_applied": {"campaign": filter_campaign} if filter_campaign else {},
        "results": [],
    }

    for row in result.get("rows", []):
        dimension_values = row.get("dimension_values", [])
        metric_values = row.get("metric_values", [])

        entry = {
            group_by: dimension_values[0].get("value") if dimension_values else None,
        }
        for i, metric_name in enumerate(ADS_METRICS):
            if i < len(metric_values):
                entry[metric_name] = metric_values[i].get("value")

        formatted["results"].append(entry)

    formatted["total_results"] = len(formatted["results"])

    # Add note if no results
    if not formatted["results"]:
        formatted["note"] = "No Google Ads data found. Ensure Google Ads is linked to this GA4 property."

    return formatted


# =============================================================================
# GOOGLE ADS VS OTHER CHANNELS COMPARISON
# =============================================================================

@mcp.tool(
    description="""Compare Google Ads performance against other traffic channels.

Shows how Google Ads stacks up against organic search, direct, social, etc.

## Returns
Per channel:
- sessions: Total visits
- totalUsers: Unique visitors
- keyEvents: Conversions
- engagementRate: Engaged session percentage
- bounceRate: Single-page visit percentage

## Parameters

### start_date / end_date (string)
Valid: "today", "yesterday", "7daysAgo", "30daysAgo", or "YYYY-MM-DD"

### limit (integer, default: 10)
Number of channels to return.

### sort_by (string, default: "sessions")
- "sessions", "users", "key_events", "engagement_rate", "bounce_rate"

## Examples
- Channel comparison: get_ads_vs_other_channels()
- By conversions: get_ads_vs_other_channels(sort_by="key_events")
- Last 7 days: get_ads_vs_other_channels(start_date="7daysAgo")

## Note
Uses GA4's default channel grouping. "Paid Search" typically represents Google Ads search traffic.
"""
)
async def get_ads_vs_other_channels(
    start_date: str = "30daysAgo",
    end_date: str = "today",
    limit: int = 10,
    sort_by: Literal["sessions", "users", "key_events", "engagement_rate", "bounce_rate"] = "sessions",
) -> Dict[str, Any]:
    """Compare Google Ads performance against other channels."""

    _validate_date_format(start_date)
    _validate_date_format(end_date)

    sort_metric = ADS_SORT_BY_MAP.get(sort_by, "sessions")

    request = data_v1beta.RunReportRequest(
        property=get_property_id(),
        date_ranges=[
            data_v1beta.DateRange(start_date=start_date, end_date=end_date)
        ],
        dimensions=[data_v1beta.Dimension(name="sessionDefaultChannelGroup")],
        metrics=[data_v1beta.Metric(name=m) for m in ADS_METRICS],
        order_bys=[
            data_v1beta.OrderBy(
                metric=data_v1beta.OrderBy.MetricOrderBy(metric_name=sort_metric),
                desc=True,
            )
        ],
        limit=limit,
    )

    response = await create_data_api_client().run_report(request)
    result = proto_to_dict(response)

    formatted = {
        "date_range": {"start": start_date, "end": end_date},
        "sort_by": sort_by,
        "channels": [],
        "summary": {},
    }

    paid_search_metrics = None
    total_sessions = 0

    for row in result.get("rows", []):
        dimension_values = row.get("dimension_values", [])
        metric_values = row.get("metric_values", [])

        channel = dimension_values[0].get("value") if dimension_values else None
        sessions = int(metric_values[0].get("value", 0)) if metric_values else 0

        entry = {
            "channel": channel,
        }
        for i, metric_name in enumerate(ADS_METRICS):
            if i < len(metric_values):
                entry[metric_name] = metric_values[i].get("value")

        formatted["channels"].append(entry)
        total_sessions += sessions

        # Track Paid Search (typically Google Ads)
        if channel and channel.lower() == "paid search":
            paid_search_metrics = entry

    # Calculate summary
    if paid_search_metrics and total_sessions > 0:
        paid_sessions = int(paid_search_metrics.get("sessions", 0))
        formatted["summary"] = {
            "paid_search_sessions": paid_sessions,
            "paid_search_share": round((paid_sessions / total_sessions) * 100, 1),
            "total_sessions": total_sessions,
        }

    formatted["total_channels"] = len(formatted["channels"])

    return formatted
