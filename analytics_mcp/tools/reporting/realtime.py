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

"""Tools for running realtime reports using the Data API."""

from typing import Any, Dict, List

from analytics_mcp.coordinator import mcp
from analytics_mcp.tools.utils import (
    create_data_api_client,
    get_property_id,
    proto_to_dict,
)
from google.analytics import data_v1beta


_RUN_REALTIME_REPORT_DESCRIPTION = """Run a GA4 realtime report showing live user activity.

For filter/orderby JSON examples, call get_api_hints first.

Args:
  dimensions: Realtime dimension names from https://developers.google.com/analytics/devguides/reporting/data/v1/realtime-api-schema#dimensions
  metrics: Realtime metric names from https://developers.google.com/analytics/devguides/reporting/data/v1/realtime-api-schema#metrics
  dimension_filter: FilterExpression for dimensions (get_api_hints for examples)
  metric_filter: FilterExpression for metrics (get_api_hints for examples)
  order_bys: List of OrderBy objects (get_api_hints for examples)
  limit: Max rows (1-250000)
  offset: Starting row (0-indexed)
  return_property_quota: Include quota info

Note: Realtime reports don't use date_ranges and can't use custom metrics.
For user-scoped custom dimensions, use get_custom_dimensions_and_metrics (look for "customUser:" prefix).
"""


async def run_realtime_report(
    dimensions: List[str],
    metrics: List[str],
    dimension_filter: Dict[str, Any] = None,
    metric_filter: Dict[str, Any] = None,
    order_bys: List[Dict[str, Any]] = None,
    limit: int = None,
    offset: int = None,
    return_property_quota: bool = False,
) -> Dict[str, Any]:
    """Runs a Google Analytics Data API realtime report."""
    request = data_v1beta.RunRealtimeReportRequest(
        property=get_property_id(),
        dimensions=[
            data_v1beta.Dimension(name=dimension) for dimension in dimensions
        ],
        metrics=[data_v1beta.Metric(name=metric) for metric in metrics],
        return_property_quota=return_property_quota,
    )

    if dimension_filter:
        request.dimension_filter = data_v1beta.FilterExpression(
            dimension_filter
        )

    if metric_filter:
        request.metric_filter = data_v1beta.FilterExpression(metric_filter)

    if order_bys:
        request.order_bys = [
            data_v1beta.OrderBy(order_by) for order_by in order_bys
        ]

    if limit:
        request.limit = limit
    if offset:
        request.offset = offset

    response = await create_data_api_client().run_realtime_report(request)
    return proto_to_dict(response)


mcp.add_tool(
    run_realtime_report,
    title="Run a Google Analytics realtime report",
    description=_RUN_REALTIME_REPORT_DESCRIPTION,
)
