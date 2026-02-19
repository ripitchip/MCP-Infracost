from fastapi import APIRouter, Query
import httpx
import os

router = APIRouter()

PROVIDER_CONFIG = {
    "gcp": {
        "vendor": "gcp",
        "service": "Compute Engine",
        "product_family": "Compute Instance",
        "regions": {"france": "europe-west9", "europe": "europe-west1", "us": "us-central1"},
        "instance_attr": "machineType",
        "default_instance": "n2-standard-2"
    },
    "aws": {
        "vendor": "aws",
        "service": "AmazonEC2",
        "product_family": "Compute Instance",
        "regions": {"france": "eu-west-3", "europe": "eu-central-1", "us": "us-east-1"},
        "cpu_attr": "vcpu",
        "instance_attr": "instanceType",
        "default_instance": "m5.large"
    },
    "azure": {
        "vendor": "azure",
        "service": "Virtual Machines",
        "product_family": "Compute",
        "regions": {"france": "francecentral", "europe": "westeurope", "us": "eastus"},
        "instance_attr": "armSkuName",
        "cpu_attr": "numberOfCores",
        "default_instance": "Standard_D2s_v5"
    }
}


@router.get("/infracost/prices")
async def get_infrastructure_prices(
    provider: str = Query("aws"),
    location: str = Query("france"),
    cores: int = Query(2),
    instance_type: str = Query(None),
    operating_system: str = Query("Linux", alias="os")
) -> dict:
    prov = provider.lower()
    conf = PROVIDER_CONFIG.get(prov)
    if not conf:
        return {"error": "Provider non supporté"}

    region = conf["regions"].get(location.lower(), location)
    attribute_filters = []

    if prov == "azure":
        target_sku = instance_type or conf["default_instance"]
        attribute_filters.append({"key": "numberOfCores", "value": str(cores)})
        attribute_filters.append({"key": "tier", "value": "Standard"})
        attribute_filters.append({"key": "armSkuName", "value": target_sku})

        try:
            serie_part = target_sku.split('_')[1]
            version_part = target_sku.split('_')[2]
            serie_name = ''.join([i for i in serie_part if not i.isdigit()])
            full_serie = f"{serie_name}{version_part} Series"
            product_name = f"Virtual Machines {full_serie}"
            if operating_system.lower() == "windows":
                product_name += " Windows"
            attribute_filters.append(
                {"key": "productName", "value": product_name})
        except Exception as e:
            print(e)
            pass

    elif prov == "gcp":
        attribute_filters.append(
            {"key": conf["instance_attr"], "value": instance_type or conf["default_instance"]})
    else:  # AWS
        attribute_filters.append(
            {"key": "operatingSystem", "value": operating_system})
        attribute_filters.append(
            {"key": conf["cpu_attr"], "value": str(cores)})
        attribute_filters.append(
            {"key": conf["instance_attr"], "value": instance_type or conf["default_instance"]})

    graphql_query = """
    query($vendor: String!, $service: String!, $region: String!, $family: String, $attrFilters: [AttributeFilter]) {
      products(filter: { vendorName: $vendor, service: $service, region: $region, productFamily: $family, attributeFilters: $attrFilters }) {
        attributes { key value }
        prices(filter: { purchaseOption: "on_demand" }) { USD unit }
      }
    }
    """

    variables = {
        "vendor": conf["vendor"],
        "service": conf["service"],
        "region": region,
        "family": conf.get("product_family"),
        "attrFilters": attribute_filters
    }

    api_key = os.getenv("INFRACOST_API_KEY")
    if not api_key:
        return {"error": "INFRACOST_API_KEY is not set"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                os.getenv("INFRACOST_API_URL",
                          "https://pricing.api.infracost.io/graphql"),
                headers={"X-Api-Key": api_key,
                         "Content-Type": "application/json"},
                json={"query": graphql_query, "variables": variables}
            )
            data = response.json()
            raw_products = data.get("data", {}).get("products") or []

            return {"provider": provider, "results_count": len(raw_products), "results": raw_products[:5]}
        except Exception as e:
            return {"error": str(e)}
