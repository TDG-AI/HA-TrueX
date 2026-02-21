"""Config flow for TrueX Smart Home integration."""

from __future__ import annotations

from typing import Any

from .truex_sharing import CustomerApi, TrueXAPIError

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_API_URL,
    CONF_CLIENT_ID,
    CONF_SCHEMA,
    CONF_SECRET,
    CONF_TOKEN_INFO,
    CONF_UID,
    CONF_USERNAME,
    DEFAULT_API_URL,
    DOMAIN,
    LOGGER,
)


class TrueXConfigFlow(ConfigFlow, domain=DOMAIN):
    """TrueX config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user step — collect credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_url = user_input[CONF_API_URL]
            client_id = user_input[CONF_CLIENT_ID]
            secret = user_input[CONF_SECRET]
            schema = user_input[CONF_SCHEMA]
            username = user_input[CONF_USERNAME]

            # Validate credentials
            api = CustomerApi(api_url, client_id, secret, schema)
            try:
                # Step 1: Get access token
                await api.get_access_token()

                # Step 2: Look up user
                user_response = await api.get_user_by_username(username)

                if not user_response.get("success"):
                    errors["base"] = "invalid_user"
                else:
                    user_list = user_response.get("result", {}).get("list", [])
                    if not user_list:
                        errors["base"] = "user_not_found"
                    else:
                        uid = user_list[0].get("uid", "")
                        if not uid:
                            errors["base"] = "user_not_found"
                        else:
                            # Success!
                            await self.async_set_unique_id(f"truex_{uid}")
                            self._abort_if_unique_id_configured()

                            entry_data = {
                                CONF_API_URL: api_url,
                                CONF_CLIENT_ID: client_id,
                                CONF_SECRET: secret,
                                CONF_SCHEMA: schema,
                                CONF_USERNAME: username,
                                CONF_UID: uid,
                                CONF_TOKEN_INFO: api.token_info.to_dict(),
                            }
                            return self.async_create_entry(
                                title=f"TrueX ({username})",
                                data=entry_data,
                            )

            except TrueXAPIError as exc:
                LOGGER.error("API error during setup: %s", exc)
                errors["base"] = "cannot_connect"
            except Exception:
                LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"
            finally:
                await api.close()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_URL,
                        default=(user_input or {}).get(CONF_API_URL, DEFAULT_API_URL),
                    ): str,
                    vol.Required(
                        CONF_CLIENT_ID,
                        default=(user_input or {}).get(CONF_CLIENT_ID, ""),
                    ): str,
                    vol.Required(
                        CONF_SECRET,
                        default=(user_input or {}).get(CONF_SECRET, ""),
                    ): str,
                    vol.Required(
                        CONF_SCHEMA,
                        default=(user_input or {}).get(CONF_SCHEMA, ""),
                    ): str,
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, ""),
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_user()
