# CarbonLens Green Route Action

Find the greenest cloud region for your deployment by querying the CarbonLens API for real-time carbon intensity data.

## Inputs

| Name             | Required | Default                  | Description                                              |
| ---------------- | -------- | ------------------------ | -------------------------------------------------------- |
| `providers`      | Yes      |                          | Comma-separated list of cloud providers (e.g. `aws,gcp`) |
| `data-residency` | No       |                          | ISO 3166-1 alpha-2 country code to constrain regions     |
| `api-url`        | No       | `http://localhost:8000`  | CarbonLens API base URL                                 |
| `api-key`        | No       |                          | API key for authenticated access                         |

## Outputs

| Name                   | Description                                  |
| ---------------------- | -------------------------------------------- |
| `provider`             | The selected cloud provider                  |
| `region`               | The selected cloud region                    |
| `grid-zone`            | The electrical grid zone for the region      |
| `carbon-intensity`     | Current carbon intensity in gCO2eq/kWh       |
| `renewable-percentage` | Percentage of energy from renewable sources  |

## Usage

### Basic

```yaml
steps:
  - uses: carbon-mesh/route@v1
    with:
      providers: aws,gcp
      api-url: https://api.carbonlens.io
```

### With all options

```yaml
steps:
  - uses: carbon-mesh/route@v1
    id: green
    with:
      providers: aws,gcp,azure
      data-residency: DE
      api-url: https://api.carbonlens.io
      api-key: ${{ secrets.CARBON_MESH_API_KEY }}

  - name: Deploy to greenest region
    run: |
      echo "Deploying to ${{ steps.green.outputs.provider }} / ${{ steps.green.outputs.region }}"
      echo "Carbon intensity: ${{ steps.green.outputs.carbon-intensity }} gCO2eq/kWh"
      echo "Renewable energy: ${{ steps.green.outputs.renewable-percentage }}%"
```

### Use outputs in a downstream job

```yaml
jobs:
  route:
    runs-on: ubuntu-latest
    outputs:
      provider: ${{ steps.green.outputs.provider }}
      region: ${{ steps.green.outputs.region }}
    steps:
      - uses: carbon-mesh/route@v1
        id: green
        with:
          providers: aws,gcp
          api-url: https://api.carbonlens.io
          api-key: ${{ secrets.CARBON_MESH_API_KEY }}

  deploy:
    needs: route
    runs-on: ubuntu-latest
    steps:
      - name: Deploy
        run: |
          echo "Deploying to ${{ needs.route.outputs.provider }} / ${{ needs.route.outputs.region }}"
```
