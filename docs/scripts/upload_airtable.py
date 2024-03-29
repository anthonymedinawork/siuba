# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.11.5
#   kernelspec:
#     display_name: venv-siuba
#     language: python
#     name: venv-siuba
# ---

# +
import pandas as pd
import os

from airtable import Airtable
from siuba.ops.support import spec

from siuba import _, select, inner_join, unnest, mutate, left_join, filter, pipe

def strip_dict_nans(d):
    return {k: v for k, v in d.items() if not pd.isna(v)}


def get_backend_records(method_name, backends):
    return [
        {
            "method_name": method_name,
            "name": k,
            **v,
        }
        for k, v in backends.items()
    ]

def record_needs_update(src, dst):
    dst = dst.copy()
    if 'is_property' in src:
        dst.setdefault('is_property', False)
    
    
    if set(src) - set(dst):
        return True
    
    return [dst[k] for k in src] != list(src.values())
# -

air_methods = Airtable("app11UN7CECnqwlGY", "tblWsICYtRPlLYJak", os.environ["AIRTABLE_API_KEY"])
air_backends = Airtable("app11UN7CECnqwlGY", "tblbmJgafdxiJLZz4", os.environ["AIRTABLE_API_KEY"])


# +

air_methods_records = air_methods.get_all()

tbl_air_methods = (
    pd.DataFrame(air_methods_records)
    >> mutate(fields = _.fields.apply(pd.DataFrame, index = [0]))
    >> unnest("fields")
)

# +
siu_raw_spec = pd.json_normalize([{"method": k, **v} for k,v in spec.items()])

tbl_siu_methods = (siu_raw_spec
   .siu_select(-_.startswith('backend'), -_.expr_frame, -_.expr_series)
   .rename(columns = lambda s: s.replace('.', '_'))
)

tbl_joined_methods = (
    tbl_siu_methods 
    >> left_join(_, select(tbl_air_methods, _.id, _.method), ['method'])
)

methods = tbl_joined_methods >> pipe(_.to_dict(orient = "records"))


# +
raw_map = {x['fields']['method']: x['fields'] for x in air_methods_records}

inserts = []
updated = []
for entry in methods:
    fields = strip_dict_nans({k:v for k,v in entry.items() if k != "id"})
    dst_fields = raw_map.get(entry['method'], {})
    
    if record_needs_update(fields, dst_fields):
        updated.append(fields)
        air_methods.update_by_field("method", entry["method"], fields = fields)
    
    if pd.isna(entry["id"]):
        inserts.append(fields)

if inserts:
    air_methods.batch_insert(inserts)

print("Updated methods: ", ", ".join([d['method'] for d in updated]))
print("Inserted methods: ", ", ".join([d['method'] for d in inserts]))

#air_methods.batch_update(list(map(strip_dict_nans, method_inserts)))
#air_backends.batch_insert(backend_inserts)
# -

# ## Link method records to backends

air_backend_records = {x['fields']['backend_method']: x['fields'] for x in air_backends.get_all()}

siu_backend_entries = sum(
    [get_backend_records(k, entry.get('backends', [])) for k, entry in spec.items()],
    []
)

for fields in siu_backend_entries:
    indx = fields["name"] + "-" + fields["method_name"]
    dst_fields = air_backend_recods.get(indx, {})
    if not dst_fields:
        air_backends.insert(fields)

    if record_needs_update(fields, dst_fields):
        air_backends.update_by_field("backend_method", indx, fields)

all_method_entries = {entry['fields']['method']: entry['id'] for entry in air_methods.get_all()}

for entry in air_backends.get_all():
    meth_name = entry['fields']['method_name']
    meth_id = [all_method_entries[meth_name]]
    air_backends.update(entry['id'], {'method': meth_id})
