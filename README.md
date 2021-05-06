## gosuslugi-api

#### `gosuslugi-api` is a BSD licensed library written in Python.<br>it was developed to obtain data from `https://dom.gosuslugi.ru/`

### Quick start


1. Install the library:
```bash
pip install gosuslugi-api
```

2. How to use it:

```Python
from gosuslugi_api.clients import GosUslugiAPIClient
from gosuslugi_api.consts import REGION_CODES_AND_NAMES

client = GosUslugiAPIClient()

# get info about licensed houses
some_region_codes = list(REGION_CODES_AND_NAMES.keys())[:3]
licenses = list(client.get_licenses(some_region_codes))[0]
# look at the structure of rows to understand how to filter them
license_row = next(licenses.rows)

organizations = client.get_organizations(inn=license_row.inn)

# get detailed info about an organization
organization = client.get_organization(guid=organizations[0]['guid'])

house_code = license_row.gos_uslugi_house_code
not_actual_houses = client.get_not_actual_houses(house_code=house_code)
actual_houses = client.get_actual_houses(house_code=house_code)

org_guid = organization['guid']
home_managements = list(client.get_home_managements(org_guid=org_guid))

# get detailed info about a home management
home_management_guid = home_managements[0]['items'][0]['guid']
home_management = client.get_home_management(home_management_guid)
```