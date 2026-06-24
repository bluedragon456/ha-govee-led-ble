# Govee LED BLE for Home Assistant

[![HACS][hacs-badge]][hacs-url]
[![GitHub Release][release-badge]][release-url]
[![Validate][validate-badge]][validate-url]
[![Home Assistant][ha-badge]][ha-url]

Local BLE control of supported Govee LED strips from Home Assistant — no cloud dependency.

## Supported Devices

All models support on/off, brightness, RGB color, color temperature, and state readback.

- **H617A/H617E** — Bluetooth RGBIC LED Strip · 80+ preset scenes · music mode
- **H6199** — DreamView T1 · video & music modes · advanced controls

## Installation

### HACS (recommended)

1. Open **HACS** → three-dot menu → **Custom repositories**
2. Add `https://github.com/teh-hippo/ha-govee-led-ble` as **Integration**
3. Install **Govee LED BLE** and restart Home Assistant

### Manual

Copy `custom_components/ha_govee_led_ble/` into your HA `custom_components/` directory and restart.

## Configuration

The integration auto-discovers nearby supported devices. It uses BLE writes only and does not pair with, claim, or permanently reconfigure controllers, so the official Govee app remains usable and devices keep working from the app when Home Assistant is offline.

### Scenes and DIY effects

H617E is registered as an alias of the existing H617A BLE profile because available product information identifies H617A/C/E/F as the same Bluetooth-only RGBIC strip family, and the effect surface (preset scenes plus music modes) matches the H617A implementation. Built-in preset scenes are sent with the same BLE scene packets as H617A. DIY scenes are not implemented: current evidence indicates DIY/inspiration content is managed by the Govee app/community/cloud experience and the local BLE API does not expose a stable, enumerable DIY-scene catalogue suitable for maintainable Home Assistant entities.

To add manually in Home Assistant:

**Settings → Devices & Services → Add Integration → Govee LED BLE**

## Development

```bash
bash scripts/check.sh
```

Requires [uv](https://docs.astral.sh/uv/). Uses [Conventional Commits](https://www.conventionalcommits.org/).

## License

MIT

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
[release-badge]: https://img.shields.io/github/v/release/teh-hippo/ha-govee-led-ble
[release-url]: https://github.com/teh-hippo/ha-govee-led-ble/releases
[validate-badge]: https://img.shields.io/github/actions/workflow/status/teh-hippo/ha-govee-led-ble/validate.yml?branch=master&label=validate
[validate-url]: https://github.com/teh-hippo/ha-govee-led-ble/actions/workflows/validate.yml
[ha-badge]: https://img.shields.io/badge/HA-2026.3%2B-blue.svg
[ha-url]: https://www.home-assistant.io
