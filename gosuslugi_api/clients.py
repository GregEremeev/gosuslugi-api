import json
import time
import logging
from io import BytesIO
from typing import Union
from urllib.parse import urlencode
from uuid import uuid4
from zipfile import ZipFile

import requests
from openpyxl import load_workbook

from gosuslugi_api.utils import Licenses
from gosuslugi_api.consts import REGION_CODES_AND_NAMES
from gosuslugi_api.exceptions import RegionCodeIsAbsentError


logger = logging.getLogger(__name__)


def _get_body_for_logging(body: Union[bytes, str]) -> str:
    try:
        if isinstance(body, bytes):
            return (b' BODY: ' + body).decode('utf-8')
        elif isinstance(body, str):
            return ' BODY: ' + body
        else:
            return ''
    except UnicodeDecodeError:
        return ''


def _get_duration_for_logging(duration: str) -> str:
    if duration is not None:
        return ' {0:.6f}s'.format(duration)
    else:
        return ''


class HTTPClient:

    GET_HTTP_METHOD = 'GET'
    POST_HTTP_METHOD = 'POST'
    PATCH_HTTP_METHOD = 'PATCH'
    PUT_HTTP_METHOD = 'PUT'

    BODY_LESS_METHODS = [GET_HTTP_METHOD]
    LOG_REQUEST_TEMPLATE = '%(method)s %(url)s%(request_body)s%(duration)s'
    LOG_RESPONSE_TEMPLATE = (
        LOG_REQUEST_TEMPLATE
        + ' - HTTP %(status_code)s%(response_body)s%(duration)s')

    def __init__(self, timeout=3, keep_alive=False, default_headers=None):
        self.timeout = timeout
        self.keep_alive = keep_alive
        self.default_headers = default_headers or {}
        self._session = None

    def _log_request(
            self, method, url, body, duration=None, log_method=logger.info):
        message_params = {
            'method': method, 'url': url,
            'request_body': _get_body_for_logging(body),
            'duration': _get_duration_for_logging(duration)}
        log_method(self.LOG_REQUEST_TEMPLATE, message_params)

    def _log_response(self, response, duration, log_method=logger.info):
        message_params = {
            'method': response.request.method,
            'url': response.request.url,
            'request_body': _get_body_for_logging(response.request.body),
            'status_code': response.status_code,
            'response_body': _get_body_for_logging(response.content),
            'duration': _get_duration_for_logging(duration)}
        log_method(self.LOG_RESPONSE_TEMPLATE, message_params)

    def _make_request(self, method, url, **kwargs) -> requests.Response:
        kwargs.setdefault('timeout', self.timeout)
        session = self.session
        timeout = kwargs.pop('timeout', self.timeout)

        headers = self.default_headers.copy()
        headers.update(kwargs.pop('headers', {}))

        request = requests.Request(method, url, headers=headers, **kwargs)
        prepared_request = request.prepare()
        self._log_request(method, url, prepared_request.body)
        start_time = time.time()
        try:
            response = session.send(prepared_request, timeout=timeout)
            duration = time.time() - start_time
            if response.status_code >= 400:
                log_method = logging.error
            else:
                log_method = logging.debug

            self._log_response(
                response, duration=duration, log_method=log_method)
            return response
        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            if e.response:
                self._log_response(
                    e.response, duration=duration, log_method=logging.error)
            else:
                self._log_request(
                    method, url, prepared_request.body,
                    log_method=logging.exception)
            raise
        finally:
            if not self.keep_alive:
                session.close()

    @property
    def session(self) -> requests.Session:
        if self.keep_alive:
            if not self._session:
                self._session = requests.Session()
            return self._session
        else:
            return requests.Session()

    def get(self, url, params=None, **kwargs) -> requests.Response:
        if params:
            url_with_query_params = url + '?' + urlencode(params)
        else:
            url_with_query_params = url

        return self._make_request(
            self.GET_HTTP_METHOD, url_with_query_params, **kwargs)

    def post(self, url, **kwargs) -> requests.Response:
        return self._make_request(self.POST_HTTP_METHOD, url, **kwargs)

    def patch(self, url, **kwargs) -> requests.Response:
        return self._make_request(self.PATCH_HTTP_METHOD, url, **kwargs)

    def put(self, url, **kwargs) -> requests.Response:
        return self._make_request(self.PUT_HTTP_METHOD, url, **kwargs)


class GosUslugiAPIClient:

    REGION_CODES_AND_NAMES = REGION_CODES_AND_NAMES

    BASE_URL = 'https://dom.gosuslugi.ru/'
    LICENSE_UID_URL = (
        f'{BASE_URL}licenses/api/rest/services/public/'
        'licenses/region-license-xls/{}')
    DOWNLOAD_LICENSES_INFO_URL = (
        f'{BASE_URL}filestore/publicDownloadAllFilesServlet?'
        'context=licenses&uids={uid}&zipFileName={file_name}.zip')
    ORGANIZATIONS_URL = (
        f'{BASE_URL}ppa/api/rest/services/ppa/'
        'organizations/chooser/search;page=1;itemsPerPage=11')
    ORGANIZATION_URL = (
        f'{BASE_URL}ppa/api/rest/services/ppa/public/organizations'
        '/orgByGuid?organizationGuid={}')
    HOUSE_CODE_URL = (
        f'{BASE_URL}nsi/api/rest/services/nsi/fias/v4/houses?'
        'houseCodes={}&includeDuplicates=false&actual={}')
    HOME_MANAGEMENTS_URL = (
        f'{BASE_URL}homemanagement/api/rest/services/houses/public/'
        'searchByOrg?pageIndex={page_number}&elementsPerPage={elems_per_page}')
    HOME_MANAGEMENT_URL = (
        f'{BASE_URL}homemanagement/api/rest/services/'
        'houses/public/1/{}/')
    HOUSE_INFO_URL = (
        f'{BASE_URL}information-disclosure/api/rest/services/'
        'disclosures/mkd/house-info?houseGuid={}')

    ORGANIZATION_PAYLOAD_PART_1 = (
        '{"sortCriteriaList":[{"sortedBy":"organizationType",'
        '"ascending":false},'
        '{"sortedBy":"shortName","ascending":true},{"sortedBy":"fullName",'
        '"ascending":true},{"sortedBy":"parentKpp","ascending":true},'
        '{"sortedBy":"kpp","ascending":true}],"organizationStatuses":'
        '{"coll":["REGISTERED"],"operand":"OR"},"organizationTypes":'
        '{"coll":["B","L","A"],"operand":"OR"},"subordinationOrgTypeList":'
        '{"coll":["HEAD","BRANCH"],"operand":"OR"},"commonSearchString":"')
    ORGANIZATION_PAYLOAD_PART_2 = (
        '","roleConstraints":{"coll":[{"roleCode":"1",'
        '"roleStatuses":["APPROVED"]},{"roleCode":"19","roleStatuses":'
        '["APPROVED"]},{"roleCode":"20","roleStatuses":["APPROVED"]},'
        '{"roleCode":"22","roleStatuses":["APPROVED"]},'
        '{"roleCode":"21","roleStatuses":["APPROVED"]}],"operand":"OR"}}')

    def __init__(self, timeout=5, keep_alive=False):
        self._region_codes = set(self.REGION_CODES_AND_NAMES)
        self._http_client = HTTPClient(timeout=timeout, keep_alive=keep_alive)

    def _get_response_body(self, response: requests.Response):
        status_code = response.status_code
        if status_code >= 400:
            response.raise_for_status()
        elif not response.content:
            return ''
        else:
            return response.json()

    def _get_license_uids(self, region_codes):
        license_uids = {}
        for region_code in region_codes:
            if region_code < 10:
                url_region_code = f'0{region_code}'
            else:
                url_region_code = region_code
            response = self._http_client.get(
                self.LICENSE_UID_URL.format(url_region_code))
            if response.status_code != 200:
                logger.error(f'uid for {region_code} was not obtained')
            else:
                license_uids[
                    self.REGION_CODES_AND_NAMES[region_code]] = response.text

        return license_uids

    def _get_licenses_info(self, license_uids):
        licenses_info = {}
        for region_name, license_uid in license_uids.items():
            response = requests.get(
                self.DOWNLOAD_LICENSES_INFO_URL.format(
                    uid=license_uid, file_name=region_name))
            if response.status_code != 200:
                logger.error(
                    f'License info for {region_name} was not obtained')
            else:
                licenses_info[region_name] = response.content

        return licenses_info

    def _get_workbooks_from_licenses_info(self, licenses_info):
        for region_name, zip_content in licenses_info.items():
            zip_file = ZipFile(BytesIO(zip_content))
            for name in zip_file.namelist():
                if name.endswith('.xlsx'):
                    xlsx_content = BytesIO(zip_file.open(name).read())
                    workbook = load_workbook(xlsx_content, read_only=True)
                    yield Licenses(region_name=region_name, workbook=workbook)

    def get_licenses(self, region_codes):
        for region_code in region_codes:
            if region_code not in REGION_CODES_AND_NAMES:
                raise RegionCodeIsAbsentError(
                    f'Region code {region_code} is absent in reference')

        license_uids = self._get_license_uids(region_codes)
        licenses_info = self._get_licenses_info(license_uids)
        return self._get_workbooks_from_licenses_info(licenses_info)

    def get_organizations(self, inn):
        payload = self.ORGANIZATION_PAYLOAD_PART_1 + str(inn)
        payload += self.ORGANIZATION_PAYLOAD_PART_2

        url = self.ORGANIZATIONS_URL
        headers = {'Content-Type': 'application/json'}
        response = self._http_client.post(url, data=payload, headers=headers)
        return self._get_response_body(response)

    def get_organization(self, guid):
        url = self.ORGANIZATION_URL.format(guid)
        return self._get_response_body(self._http_client.get(url))

    def get_not_actual_houses(self, house_code):
        url = self.HOUSE_CODE_URL.format(house_code, 'false')
        return self._get_response_body(self._http_client.get(url))

    def get_actual_houses(self, house_code):
        url = self.HOUSE_CODE_URL.format(house_code, 'true')
        return self._get_response_body(self._http_client.get(url))

    def get_home_managements(self, org_guid, start_page=1, per_page=1):
        url = self.HOME_MANAGEMENTS_URL.format(
            page_number=start_page, elems_per_page=per_page)
        payload = json.dumps({'organizationGuid': org_guid, 'calcCount': True})
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, data=payload, headers=headers)
        json_body = self._get_response_body(response)
        yield json_body
        objects_number = json_body['total'] or 0
        for page_num in range(2, objects_number + 1):
            url = self.HOME_MANAGEMENTS_URL.format(
                page_number=page_num, elems_per_page=per_page)
            response = requests.post(url, data=payload, headers=headers)
            yield self._get_response_body(response)

    def get_home_management(self, home_management_guid):
        url = self.HOME_MANAGEMENT_URL.format(home_management_guid)
        return self._get_response_body(requests.get(url))

    def get_house_info(self, house_guid):
        headers = {
            'Session-GUID': str(uuid4()),
            'Request-GUID': str(uuid4())
        }
        url = self.HOUSE_INFO_URL.format(house_guid)
        return self._get_response_body(requests.get(url, headers=headers))
