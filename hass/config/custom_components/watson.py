import homeassistant.loader as loader

DOMAIN = 'watson'

# List of component names (string) your component depends upon.
DEPENDENCIES = ['rest']

DEFAULT_APIKEY = '*'

def setup(hass, config):
    hass.states.set('watson', 'online')

    # """Set up the Hello MQTT component."""
    # rest = loader.get_component('rest')

    apikey = config[DOMAIN].get('wiotp_api_key', DEFAULT_APIKEY)
    orgid = config[DOMAIN].get('wiotp_ord_id', null)
    auth_token = config[DOMAIN].get('wiotp_auth_token', null)
    device_type = config[DOMAIN].get('wiotp_device_type', null)
    device_token = config[DOMAIN].get('wiotp_device_auth_token', null)

    entity_id = 'watson.apikey'
    hass.states.set(entity_id, apikey)

    # Listener to be called when we receive a message.
    def message_received(topic, payload, qos):
        """Handle new MQTT messages."""
        hass.states.set(entity_id, payload)

    # Service to publish a message on MQTT.
    def set_state_service(call):
        """Service to send a message."""
        mqtt.publish(hass, topic, call.data.get('new_state'))

    # Register our service with Home Assistant.
    hass.services.register(DOMAIN, 'set_state', set_state_service)

    # Return boolean to indicate that initialization was successfully.
    return True

