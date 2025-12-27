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

"""PM-friendly tools for audience/demographics reporting."""

from typing import Any, Dict, Literal

from analytics_mcp.coordinator import mcp
from analytics_mcp.tools.utils import (
    create_data_api_client,
    get_property_id,
    proto_to_dict,
)
from analytics_mcp.tools.reporting.acquisition import _validate_date_format
from google.analytics import data_v1beta


# Mapping for demographics dimensions
DEMOGRAPHICS_DIMENSION_MAP = {
    "country": "country",
    "city": "city",
    "device": "deviceCategory",
    "browser": "browser",
    "os": "operatingSystem",
    "language": "language",
}

# Mapping for demographics sort metrics
DEMOGRAPHICS_SORT_METRIC_MAP = {
    "users": "totalUsers",
    "sessions": "sessions",
    "engagement_rate": "engagementRate",
    "bounce_rate": "bounceRate",
}

# Metrics for demographics reports
DEMOGRAPHICS_METRICS = [
    "totalUsers",
    "sessions",
    "engagementRate",
    "bounceRate",
    "screenPageViews",
]


@mcp.tool(
    description="""Get user demographics: who are your visitors (country, device, browser, etc).

Shows audience breakdown by geographic and technical attributes.

## Returns
- totalUsers: Unique visitors
- sessions: Total visits
- engagementRate: Percentage of engaged sessions
- bounceRate: Percentage of single-page visits
- screenPageViews: Total page views

## Parameters

### group_by (string, default: "country")
- "country": User's country (e.g., "United States", "India")
- "city": User's city (e.g., "New York", "London")
- "device": Device type (Desktop, Mobile, Tablet)
- "browser": Browser name (Chrome, Safari, Firefox)
- "os": Operating system (Windows, iOS, Android, macOS)
- "language": Browser language setting (en-us, es, fr)

### start_date / end_date (string)
Valid: "today", "yesterday", "7daysAgo", "30daysAgo", or "YYYY-MM-DD"

### limit (integer, default: 10)
Number of results to return (1-100).

### sort_by (string, default: "users")
- "users": Sort by unique visitors
- "sessions": Sort by session count
- "engagement_rate": Sort by engagement rate
- "bounce_rate": Sort by bounce rate

## Examples
- Top countries: get_user_demographics()
- Device breakdown: get_user_demographics(group_by="device")
- Top browsers: get_user_demographics(group_by="browser", limit=5)
- Mobile vs Desktop: get_user_demographics(group_by="device", sort_by="sessions")

## Note
This shows audience attributes. For traffic sources, use get_acquisition_report instead.
"""
)
async def get_user_demographics(
    group_by: Literal["country", "city", "device", "browser", "os", "language"] = "country",
    start_date: str = "30daysAgo",
    end_date: str = "today",
    limit: int = 10,
    sort_by: Literal["users", "sessions", "engagement_rate", "bounce_rate"] = "users",
) -> Dict[str, Any]:
    """Get user demographics report showing audience breakdown."""

    # Validate inputs
    _validate_date_format(start_date)
    _validate_date_format(end_date)

    if group_by not in DEMOGRAPHICS_DIMENSION_MAP:
        raise ValueError(f"Invalid group_by: '{group_by}'. Valid options: {list(DEMOGRAPHICS_DIMENSION_MAP.keys())}")

    if sort_by not in DEMOGRAPHICS_SORT_METRIC_MAP:
        raise ValueError(f"Invalid sort_by: '{sort_by}'. Valid options: {list(DEMOGRAPHICS_SORT_METRIC_MAP.keys())}")

    dimension_name = DEMOGRAPHICS_DIMENSION_MAP[group_by]
    sort_metric = DEMOGRAPHICS_SORT_METRIC_MAP[sort_by]

    request = data_v1beta.RunReportRequest(
        property=get_property_id(),
        date_ranges=[
            data_v1beta.DateRange(start_date=start_date, end_date=end_date)
        ],
        dimensions=[data_v1beta.Dimension(name=dimension_name)],
        metrics=[data_v1beta.Metric(name=m) for m in DEMOGRAPHICS_METRICS],
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

    # Format response for PM-friendly output
    formatted = {
        "date_range": {"start": start_date, "end": end_date},
        "group_by": group_by,
        "sort_by": sort_by,
        "results": [],
    }

    for row in result.get("rows", []):
        dimension_values = row.get("dimension_values", [])
        metric_values = row.get("metric_values", [])

        entry = {
            group_by: dimension_values[0].get("value") if dimension_values else None,
        }
        for i, metric_name in enumerate(DEMOGRAPHICS_METRICS):
            if i < len(metric_values):
                entry[metric_name] = metric_values[i].get("value")

        formatted["results"].append(entry)

    formatted["total_results"] = len(formatted["results"])

    return formatted
