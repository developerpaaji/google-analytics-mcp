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

Returns: totalUsers, sessions, engagementRate, bounceRate, screenPageViews

group_by: "country" (default), "city", "device", "browser", "os", "language"
sort_by: "users" (default), "sessions", "engagement_rate", "bounce_rate"

For traffic sources, use get_acquisition_report instead."""
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


# =============================================================================
# RETENTION
# =============================================================================

# Metrics for retention reports
RETENTION_METRICS = [
    "totalUsers",
    "newUsers",
    "activeUsers",
    "userEngagementDuration",
]


@mcp.tool(
    description="""Get user retention: new vs returning users and engagement patterns.

Returns: totalUsers, newUsers, activeUsers, userEngagementDuration, returning_users, returning_rate

retention_type: "new_vs_returning" (default), "by_first_visit" (cohort)
granularity: "day" (default), "week", "month" (for by_first_visit only)

For detailed cohort curves, use GA4 Exploration in the UI."""
)
async def get_retention(
    retention_type: Literal["new_vs_returning", "by_first_visit"] = "new_vs_returning",
    start_date: str = "30daysAgo",
    end_date: str = "today",
    granularity: Literal["day", "week", "month"] = "day",
) -> Dict[str, Any]:
    """Get user retention report showing new vs returning users."""

    _validate_date_format(start_date)
    _validate_date_format(end_date)

    if retention_type == "by_first_visit":
        # Cohort-style: group by first session date
        granularity_dimension_map = {
            "day": "firstSessionDate",
            "week": "firstSessionDate",
            "month": "firstSessionDate",
        }
        dimension_name = granularity_dimension_map.get(granularity, "firstSessionDate")

        request = data_v1beta.RunReportRequest(
            property=get_property_id(),
            date_ranges=[
                data_v1beta.DateRange(start_date=start_date, end_date=end_date)
            ],
            dimensions=[data_v1beta.Dimension(name=dimension_name)],
            metrics=[data_v1beta.Metric(name=m) for m in RETENTION_METRICS],
            order_bys=[
                data_v1beta.OrderBy(
                    dimension=data_v1beta.OrderBy.DimensionOrderBy(
                        dimension_name=dimension_name
                    ),
                    desc=False,
                )
            ],
        )

        response = await create_data_api_client().run_report(request)
        result = proto_to_dict(response)

        formatted = {
            "date_range": {"start": start_date, "end": end_date},
            "retention_type": retention_type,
            "granularity": granularity,
            "cohorts": [],
        }

        for row in result.get("rows", []):
            dimension_values = row.get("dimension_values", [])
            metric_values = row.get("metric_values", [])

            cohort_date = dimension_values[0].get("value") if dimension_values else None
            total_users = int(metric_values[0].get("value", 0)) if metric_values else 0
            new_users = int(metric_values[1].get("value", 0)) if len(metric_values) > 1 else 0

            entry = {
                "first_visit_date": cohort_date,
                "totalUsers": total_users,
                "newUsers": new_users,
                "activeUsers": int(metric_values[2].get("value", 0)) if len(metric_values) > 2 else 0,
                "userEngagementDuration": metric_values[3].get("value") if len(metric_values) > 3 else "0",
            }

            formatted["cohorts"].append(entry)

        formatted["total_cohorts"] = len(formatted["cohorts"])

    else:
        # Simple new vs returning breakdown
        request = data_v1beta.RunReportRequest(
            property=get_property_id(),
            date_ranges=[
                data_v1beta.DateRange(start_date=start_date, end_date=end_date)
            ],
            dimensions=[data_v1beta.Dimension(name="newVsReturning")],
            metrics=[data_v1beta.Metric(name=m) for m in RETENTION_METRICS],
        )

        response = await create_data_api_client().run_report(request)
        result = proto_to_dict(response)

        formatted = {
            "date_range": {"start": start_date, "end": end_date},
            "retention_type": retention_type,
            "breakdown": [],
            "summary": {},
        }

        total_all_users = 0
        new_users_count = 0
        returning_users_count = 0

        for row in result.get("rows", []):
            dimension_values = row.get("dimension_values", [])
            metric_values = row.get("metric_values", [])

            user_type = dimension_values[0].get("value") if dimension_values else None
            users = int(metric_values[0].get("value", 0)) if metric_values else 0

            entry = {
                "user_type": user_type,
                "totalUsers": users,
                "activeUsers": int(metric_values[2].get("value", 0)) if len(metric_values) > 2 else 0,
                "userEngagementDuration": metric_values[3].get("value") if len(metric_values) > 3 else "0",
            }

            if user_type == "new":
                new_users_count = users
            elif user_type == "returning":
                returning_users_count = users

            total_all_users += users
            formatted["breakdown"].append(entry)

        # Calculate summary
        formatted["summary"] = {
            "total_users": total_all_users,
            "new_users": new_users_count,
            "returning_users": returning_users_count,
            "new_user_rate": round((new_users_count / total_all_users) * 100, 1) if total_all_users > 0 else 0,
            "returning_rate": round((returning_users_count / total_all_users) * 100, 1) if total_all_users > 0 else 0,
        }

    return formatted
