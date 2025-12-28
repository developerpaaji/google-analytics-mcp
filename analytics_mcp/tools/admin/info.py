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

"""Tools for gathering Google Analytics account and property information."""

from typing import Any, Dict

from analytics_mcp.coordinator import mcp
from analytics_mcp.tools.utils import (
    create_admin_api_client,
    get_property_id,
    proto_to_dict,
)
from google.analytics import admin_v1beta


@mcp.tool(
    description="Get details about the configured GA4 property (name, timezone, currency, industry, etc)."
)
async def get_property_details() -> Dict[str, Any]:
    """Returns details about the configured property."""
    client = create_admin_api_client()
    request = admin_v1beta.GetPropertyRequest(
        name=get_property_id()
    )
    response = await client.get_property(request=request)
    return proto_to_dict(response)
