from datetime import datetime

from dataclasses import dataclass, asdict

from gosuslugi_api.exceptions import WorksheetAbsentError


class Licenses:

    def __init__(self, region_name, workbook):
        self.region_name = region_name
        self.workbook = workbook

    @property
    def rows(self):
        worksheets = self.workbook.worksheets
        if not worksheets:
            raise WorksheetAbsentError('There is no any worksheet')
        rows = worksheets[0].rows
        _skip_header_in_license_rows(rows)
        for row in rows:
            yield _make_gis_gkh_row(row)


def _skip_header_in_license_rows(license_rows):
    for row in license_rows:
        cell_value = row[0].value
        if cell_value and cell_value.strip().lower() == 'номер лицензии':
            break


def _make_gis_gkh_row(row):
    row_number = row[0].row
    values_from_all_cells = [cell.value for cell in row]
    not_empty_values = values_from_all_cells[:-2]
    house_fias_id_stub = ''
    return LicensesFileRow(row_number, house_fias_id_stub, *not_empty_values)


@dataclass
class LicensesFileRow:

    number_in_file: int
    house_fias_id: str
    license_number: str = ''
    license_date: str = ''
    license_status: str = ''
    license_included_date: str = ''
    order_number: str = ''
    order_date: str = ''
    lisence_juristic_address: str = ''
    license_holder_uid: str = ''
    additional_info: str = ''
    license_holder_name: str = ''
    inn: str = ''
    ogrn: str = ''
    mkd_address: str = ''
    gos_uslugi_house_code: str = ''
    mkd_included_register_date: datetime = None
    mkd_begin_management_date: datetime = None
    mkd_end_management_date: datetime = None
    mkd_excluded_register_date: datetime = None
    mkd_excluded_reason: str = ''
    state_198_info: str = ''
    is_information_in_register: bool = None

    datetime_format_fields = (
        'mkd_excluded_register_date', 'mkd_included_register_date')
    date_format_fields = (
        'mkd_end_management_date', 'mkd_begin_management_date')
    in_register_mark = 'размещена'
    active_license_status = 'действующая'

    def __post_init__(self):
        for field_name, field_value in asdict(self).items():
            if isinstance(field_value, str):
                field_value = field_value.strip().lower()
            if field_name in self.datetime_format_fields:
                if field_value:
                    field_value = datetime.strptime(
                        field_value, '%d.%m.%Y %H:%M:%S')
                else:
                    field_value = datetime.max
            if field_name in self.date_format_fields:
                if field_value:
                    field_value = datetime.strptime(field_value, '%d.%m.%Y')
                else:
                    field_value = datetime.max
            if field_name == 'is_information_in_register':
                field_value = field_value == self.in_register_mark
            setattr(self, field_name, field_value)
