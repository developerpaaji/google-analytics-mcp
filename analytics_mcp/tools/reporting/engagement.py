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

"""PM-friendly tools for engagement and content reporting."""

from typing import Any, Dict, List, Literal, Optional

from analytics_mcp.coordinator import mcp
from analytics_mcp.tools.utils import (
    create_data_api_client,
    get_property_id,
    proto_to_dict,
)
from analytics_mcp.tools.reporting.acquisition import _validate_date_format
from google.analytics import data_v1beta


# Mapping for page report dimensions
PAGE_TYPE_DIMENSION_MAP = {
    "all": "pagePath",
    "landing_pages": "landingPage",
    "exit_pages": "exitPage",
}

# Mapping for page sort metrics
PAGE_SORT_METRIC_MAP = {
    "views": "screenPageViews",
    "users": "totalUsers",
    "engagement_time": "userEngagementDuration",
    "bounce_rate": "bounceRate",
}

# Metrics for page reports
PAGE_METRICS = [
    "screenPageViews",
    "totalUsers",
    "userEngagementDuration",
    "bounceRate",
    "sessions",
]


@mcp.tool(
    description="""Get top pages report: which pages get the most traffic and engagement.

Shows page performance ranked by views, users, or engagement.

## Returns
- screenPageViews: Total page views
- totalUsers: Unique visitors to the page
- userEngagementDuration: Time spent on page (seconds)
- bounceRate: Percentage of single-page visits
- sessions: Number of sessions including this page

## Parameters

### page_type (string, default: "all")
- "all": All pages by URL path
- "landing_pages": First page users see when entering the site
- "exit_pages": Last page users see before leaving

### start_date / end_date (string)
Valid: "today", "yesterday", "7daysAgo", "30daysAgo", or "YYYY-MM-DD"

### limit (integer, default: 10)
Number of results to return (1-100).

### sort_by (string, default: "views")
- "views": Sort by page views
- "users": Sort by unique visitors
- "engagement_time": Sort by time on page
- "bounce_rate": Sort by bounce rate

### filter_path (string, optional)
Filter by URL path. Examples: "/blog/", "/products/", "/pricing"

### filter_hostname (string, optional)
Filter by hostname. Examples: "example.com", "blog.example.com"

## Examples
- Top 10 pages: get_top_pages()
- Top landing pages: get_top_pages(page_type="landing_pages")
- Blog pages only: get_top_pages(filter_path="/blog/")
- Most engaging pages: get_top_pages(sort_by="engagement_time", limit=20)

## Note
This shows page-level metrics. For site-wide totals, use get_traffic_overview instead.
"""
)
async def get_top_pages(
    page_type: Literal["all", "landing_pages", "exit_pages"] = "all",
    start_date: str = "30daysAgo",
    end_date: str = "today",
    limit: int = 10,
    sort_by: Literal["views", "users", "engagement_time", "bounce_rate"] = "views",
    filter_path: Optional[str] = None,
    filter_hostname: Optional[str] = None,
) -> Dict[str, Any]:
    """Get top pages report showing most visited pages."""

    # Validate inputs
    _validate_date_format(start_date)
    _validate_date_format(end_date)

    if page_type not in PAGE_TYPE_DIMENSION_MAP:
        raise ValueError(f"Invalid page_type: '{page_type}'. Valid options: {list(PAGE_TYPE_DIMENSION_MAP.keys())}")

    if sort_by not in PAGE_SORT_METRIC_MAP:
        raise ValueError(f"Invalid sort_by: '{sort_by}'. Valid options: {list(PAGE_SORT_METRIC_MAP.keys())}")

    dimension_name = PAGE_TYPE_DIMENSION_MAP[page_type]
    sort_metric = PAGE_SORT_METRIC_MAP[sort_by]

    request = data_v1beta.RunReportRequest(
        property=get_property_id(),
        date_ranges=[
            data_v1beta.DateRange(start_date=start_date, end_date=end_date)
        ],
        dimensions=[data_v1beta.Dimension(name=dimension_name)],
        metrics=[data_v1beta.Metric(name=m) for m in PAGE_METRICS],
        order_bys=[
            data_v1beta.OrderBy(
                metric=data_v1beta.OrderBy.MetricOrderBy(metric_name=sort_metric),
                desc=True,
            )
        ],
        limit=limit,
    )

    # Add filters if provided
    filters = []
    if filter_path:
        filters.append(
            data_v1beta.FilterExpression(
                filter=data_v1beta.Filter(
                    field_name=dimension_name,
                    string_filter=data_v1beta.Filter.StringFilter(
                        match_type=data_v1beta.Filter.StringFilter.MatchType.CONTAINS,
                        value=filter_path,
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

    if filters:
        if len(filters) == 1:
            request.dimension_filter = filters[0]
        else:
            request.dimension_filter = data_v1beta.FilterExpression(
                and_group=data_v1beta.FilterExpressionList(expressions=filters)
            )

    response = await create_data_api_client().run_report(request)
    result = proto_to_dict(response)

    # Format response for PM-friendly output
    formatted = {
        "date_range": {"start": start_date, "end": end_date},
        "page_type": page_type,
        "sort_by": sort_by,
        "filters_applied": {
            k: v for k, v in {
                "path": filter_path,
                "hostname": filter_hostname,
            }.items() if v is not None
        },
        "results": [],
    }

    for row in result.get("rows", []):
        dimension_values = row.get("dimension_values", [])
        metric_values = row.get("metric_values", [])

        entry = {
            "page": dimension_values[0].get("value") if dimension_values else None,
        }
        for i, metric_name in enumerate(PAGE_METRICS):
            if i < len(metric_values):
                entry[metric_name] = metric_values[i].get("value")

        formatted["results"].append(entry)

    formatted["total_results"] = len(formatted["results"])

    return formatted


# =============================================================================
# EVENTS
# =============================================================================

# Metrics for events reports
EVENTS_METRICS = [
    "eventCount",
    "totalUsers",
    "eventCountPerUser",
    "eventValue",
]


@mcp.tool(
    description="""Get events report: what actions are users taking on your site.

Shows event counts, users, and values for tracked events.

## Returns
- eventCount: Total times the event was triggered
- totalUsers: Unique users who triggered the event
- eventCountPerUser: Average events per user
- eventValue: Total value associated with events (if configured)

## Parameters

### event_type (string, default: "all")
- "all": All events tracked on the site
- "key_events_only": Only key events (formerly called conversions)

### start_date / end_date (string)
Valid: "today", "yesterday", "7daysAgo", "30daysAgo", or "YYYY-MM-DD"

### limit (integer, default: 10)
Number of results to return (1-100).

### sort_by (string, default: "count")
- "count": Sort by total event count
- "users": Sort by unique users

### filter_event (string, optional)
Filter by event name. Examples: "purchase", "sign_up", "page_view"
Partial match, case-insensitive.

## Examples
- All events: get_events()
- Key events only: get_events(event_type="key_events_only")
- Purchase events: get_events(filter_event="purchase")
- Top events by users: get_events(sort_by="users", limit=20)

## Note
This shows event-level data. For page views, use get_top_pages instead.
"""
)
async def get_events(
    event_type: Literal["all", "key_events_only"] = "all",
    start_date: str = "30daysAgo",
    end_date: str = "today",
    limit: int = 10,
    sort_by: Literal["count", "users"] = "count",
    filter_event: Optional[str] = None,
) -> Dict[str, Any]:
    """Get events report showing user actions and conversions."""

    _validate_date_format(start_date)
    _validate_date_format(end_date)

    sort_metric = "eventCount" if sort_by == "count" else "totalUsers"

    request = data_v1beta.RunReportRequest(
        property=get_property_id(),
        date_ranges=[
            data_v1beta.DateRange(start_date=start_date, end_date=end_date)
        ],
        dimensions=[data_v1beta.Dimension(name="eventName")],
        metrics=[data_v1beta.Metric(name=m) for m in EVENTS_METRICS],
        order_bys=[
            data_v1beta.OrderBy(
                metric=data_v1beta.OrderBy.MetricOrderBy(metric_name=sort_metric),
                desc=True,
            )
        ],
        limit=limit,
    )

    filters = []

    if event_type == "key_events_only":
        filters.append(
            data_v1beta.FilterExpression(
                filter=data_v1beta.Filter(
                    field_name="isKeyEvent",
                    string_filter=data_v1beta.Filter.StringFilter(
                        match_type=data_v1beta.Filter.StringFilter.MatchType.EXACT,
                        value="true",
                    ),
                )
            )
        )

    if filter_event:
        filters.append(
            data_v1beta.FilterExpression(
                filter=data_v1beta.Filter(
                    field_name="eventName",
                    string_filter=data_v1beta.Filter.StringFilter(
                        match_type=data_v1beta.Filter.StringFilter.MatchType.CONTAINS,
                        value=filter_event,
                        case_sensitive=False,
                    ),
                )
            )
        )

    if filters:
        if len(filters) == 1:
            request.dimension_filter = filters[0]
        else:
            request.dimension_filter = data_v1beta.FilterExpression(
                and_group=data_v1beta.FilterExpressionList(expressions=filters)
            )

    response = await create_data_api_client().run_report(request)
    result = proto_to_dict(response)

    formatted = {
        "date_range": {"start": start_date, "end": end_date},
        "event_type": event_type,
        "sort_by": sort_by,
        "filters_applied": {
            k: v for k, v in {
                "event_name": filter_event,
            }.items() if v is not None
        },
        "results": [],
    }

    for row in result.get("rows", []):
        dimension_values = row.get("dimension_values", [])
        metric_values = row.get("metric_values", [])

        entry = {
            "event_name": dimension_values[0].get("value") if dimension_values else None,
        }
        for i, metric_name in enumerate(EVENTS_METRICS):
            if i < len(metric_values):
                entry[metric_name] = metric_values[i].get("value")

        formatted["results"].append(entry)

    formatted["total_results"] = len(formatted["results"])

    return formatted


# =============================================================================
# FUNNEL ANALYSIS
# =============================================================================

# Common ecommerce funnel steps
ECOMMERCE_FUNNEL_EVENTS = [
    "view_item",
    "add_to_cart",
    "begin_checkout",
    "purchase",
]

# Common signup funnel steps
SIGNUP_FUNNEL_EVENTS = [
    "page_view",
    "sign_up",
    "first_open",
]


@mcp.tool(
    description="""Get funnel analysis: track user progression through a sequence of events.

Shows how many users complete each step and where they drop off.

## Returns
- steps: List of funnel steps with event counts and users
- drop_off_rate: Percentage of users lost at each step
- overall_conversion_rate: % of users who completed the entire funnel

## Parameters

### funnel_type (string, default: "ecommerce")
Pre-built funnels:
- "ecommerce": view_item → add_to_cart → begin_checkout → purchase
- "signup": page_view → sign_up → first_open

### custom_events (list, optional)
Define your own funnel with a list of event names.
Example: ["landing_page", "form_start", "form_submit", "confirmation"]

### start_date / end_date (string)
Valid: "today", "yesterday", "7daysAgo", "30daysAgo", or "YYYY-MM-DD"

## Examples
- Ecommerce funnel: get_funnel()
- Signup funnel: get_funnel(funnel_type="signup")
- Custom funnel: get_funnel(custom_events=["page_view", "click_cta", "form_submit"])
- Last 7 days: get_funnel(start_date="7daysAgo")

## Note
This uses event counts per step. For true session-based funnels with
strict ordering, use the GA4 Exploration reports in the UI.
"""
)
async def get_funnel(
    funnel_type: Literal["ecommerce", "signup"] = "ecommerce",
    custom_events: Optional[List[str]] = None,
    start_date: str = "30daysAgo",
    end_date: str = "today",
) -> Dict[str, Any]:
    """Get funnel analysis showing user progression through events."""

    _validate_date_format(start_date)
    _validate_date_format(end_date)

    # Determine which events to use
    if custom_events and len(custom_events) >= 2:
        funnel_events = custom_events
        funnel_name = "custom"
    elif funnel_type == "signup":
        funnel_events = SIGNUP_FUNNEL_EVENTS
        funnel_name = "signup"
    else:
        funnel_events = ECOMMERCE_FUNNEL_EVENTS
        funnel_name = "ecommerce"

    # Build filter for funnel events
    event_filters = [
        data_v1beta.FilterExpression(
            filter=data_v1beta.Filter(
                field_name="eventName",
                string_filter=data_v1beta.Filter.StringFilter(
                    match_type=data_v1beta.Filter.StringFilter.MatchType.EXACT,
                    value=event,
                ),
            )
        )
        for event in funnel_events
    ]

    request = data_v1beta.RunReportRequest(
        property=get_property_id(),
        date_ranges=[
            data_v1beta.DateRange(start_date=start_date, end_date=end_date)
        ],
        dimensions=[data_v1beta.Dimension(name="eventName")],
        metrics=[
            data_v1beta.Metric(name="eventCount"),
            data_v1beta.Metric(name="totalUsers"),
        ],
        dimension_filter=data_v1beta.FilterExpression(
            or_group=data_v1beta.FilterExpressionList(expressions=event_filters)
        ),
    )

    response = await create_data_api_client().run_report(request)
    result = proto_to_dict(response)

    # Build a map of event -> metrics
    event_data = {}
    for row in result.get("rows", []):
        dimension_values = row.get("dimension_values", [])
        metric_values = row.get("metric_values", [])
        if dimension_values:
            event_name = dimension_values[0].get("value")
            event_data[event_name] = {
                "eventCount": int(metric_values[0].get("value", 0)) if metric_values else 0,
                "totalUsers": int(metric_values[1].get("value", 0)) if len(metric_values) > 1 else 0,
            }

    # Build funnel steps in order
    steps = []
    previous_users = None

    for i, event in enumerate(funnel_events):
        data = event_data.get(event, {"eventCount": 0, "totalUsers": 0})
        current_users = data["totalUsers"]

        step = {
            "step": i + 1,
            "event": event,
            "eventCount": data["eventCount"],
            "users": current_users,
        }

        if previous_users is not None and previous_users > 0:
            step["conversion_rate"] = round((current_users / previous_users) * 100, 1)
            step["drop_off_rate"] = round(100 - step["conversion_rate"], 1)
        else:
            step["conversion_rate"] = 100.0
            step["drop_off_rate"] = 0.0

        steps.append(step)
        previous_users = current_users

    # Calculate overall conversion
    first_step_users = steps[0]["users"] if steps else 0
    last_step_users = steps[-1]["users"] if steps else 0
    overall_conversion = round((last_step_users / first_step_users) * 100, 1) if first_step_users > 0 else 0

    formatted = {
        "date_range": {"start": start_date, "end": end_date},
        "funnel_type": funnel_name,
        "funnel_events": funnel_events,
        "steps": steps,
        "summary": {
            "total_steps": len(steps),
            "first_step_users": first_step_users,
            "last_step_users": last_step_users,
            "overall_conversion_rate": overall_conversion,
        },
    }

    return formatted


# =============================================================================
# SITE SEARCH
# =============================================================================

# Metrics for search reports
SEARCH_METRICS = [
    "eventCount",
    "totalUsers",
]


@mcp.tool(
    description="""Get site search report: what users search for on your site.

Shows search terms users enter in your site's search box.

## Returns
- searchTerm: The search query entered by users
- eventCount: Number of times this term was searched
- totalUsers: Unique users who searched this term

## Parameters

### start_date / end_date (string)
Valid: "today", "yesterday", "7daysAgo", "30daysAgo", or "YYYY-MM-DD"

### limit (integer, default: 20)
Number of results to return (1-100).

### sort_by (string, default: "count")
- "count": Sort by search frequency
- "users": Sort by unique users

### filter_term (string, optional)
Filter by search term. Partial match, case-insensitive.

## Examples
- Top search terms: get_site_search()
- Last 7 days: get_site_search(start_date="7daysAgo")
- Search for specific term: get_site_search(filter_term="pricing")

## Note
Requires site search tracking to be configured in GA4.
If no results, site search may not be set up for this property.
"""
)
async def get_site_search(
    start_date: str = "30daysAgo",
    end_date: str = "today",
    limit: int = 20,
    sort_by: Literal["count", "users"] = "count",
    filter_term: Optional[str] = None,
) -> Dict[str, Any]:
    """Get site search report showing what users search for."""

    _validate_date_format(start_date)
    _validate_date_format(end_date)

    sort_metric = "eventCount" if sort_by == "count" else "totalUsers"

    request = data_v1beta.RunReportRequest(
        property=get_property_id(),
        date_ranges=[
            data_v1beta.DateRange(start_date=start_date, end_date=end_date)
        ],
        dimensions=[data_v1beta.Dimension(name="searchTerm")],
        metrics=[data_v1beta.Metric(name=m) for m in SEARCH_METRICS],
        order_bys=[
            data_v1beta.OrderBy(
                metric=data_v1beta.OrderBy.MetricOrderBy(metric_name=sort_metric),
                desc=True,
            )
        ],
        limit=limit,
    )

    # Add filter if provided
    if filter_term:
        request.dimension_filter = data_v1beta.FilterExpression(
            filter=data_v1beta.Filter(
                field_name="searchTerm",
                string_filter=data_v1beta.Filter.StringFilter(
                    match_type=data_v1beta.Filter.StringFilter.MatchType.CONTAINS,
                    value=filter_term,
                    case_sensitive=False,
                ),
            )
        )

    response = await create_data_api_client().run_report(request)
    result = proto_to_dict(response)

    formatted = {
        "date_range": {"start": start_date, "end": end_date},
        "sort_by": sort_by,
        "filter_applied": filter_term,
        "results": [],
    }

    for row in result.get("rows", []):
        dimension_values = row.get("dimension_values", [])
        metric_values = row.get("metric_values", [])

        search_term = dimension_values[0].get("value") if dimension_values else None

        # Skip empty or (not set) terms
        if not search_term or search_term == "(not set)":
            continue

        entry = {
            "searchTerm": search_term,
            "eventCount": int(metric_values[0].get("value", 0)) if metric_values else 0,
            "totalUsers": int(metric_values[1].get("value", 0)) if len(metric_values) > 1 else 0,
        }

        formatted["results"].append(entry)

    formatted["total_results"] = len(formatted["results"])

    return formatted
