import csv
from dataclasses import dataclass
import io
import json
from pathlib import Path
import struct

import pytest

from lunar_data.lend import LendProduct,LendCollection,CHANNEL_OFFSETS
from lunar_data.csv_export import render_csv


@pytest.fixture
def synthetic_lend(tmp_path):
    name='lend_rdr_alde_20090915'
    xml=tmp_path/(name+'.xml');dat=xml.with_suffix('.dat')
    fields={'LUNARCENTRIC_LATITUDE':46,'LUNARCENTIC_EAST_LONGITUDE':50}
    for channel,offset in CHANNEL_OFFSETS.items():
        for suffix,delta in [('EXPOSURE',0),('RATE',4),('ERR',8)]:fields[channel+'_'+suffix]=offset+delta
    xml.write_text('<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">'
        '<logical_identifier>synthetic:lend</logical_identifier>'
        '<start_date_time>2009-09-15T00:00:00Z</start_date_time><stop_date_time>2011-12-11T00:00:00Z</stop_date_time>'
        f'<file_name>{name}.dat</file_name><offset>0</offset><records>57600</records>'
        '<Record_Binary><record_length>310</record_length>'+
        ''.join(f'<Field_Binary><name>{name}</name><field_location>{offset+1}</field_location>'
                '<field_length>23</field_length><data_type>ASCII_String</data_type></Field_Binary>'
                for name,offset in [('START_UTC_TIME',0),('STOP_UTC_TIME',23)])+
        ''.join(f'<Field_Binary><name>{k}</name><field_location>{v+1}</field_location>'
                '<field_length>4</field_length><data_type>IEEE754MSBSingle</data_type>'+
                ('<unit>s</unit>' if k.endswith('EXPOSURE') else '')+'</Field_Binary>' for k,v in fields.items())+
        '</Record_Binary></Product_Observational>',encoding='utf-8')
    xml.with_suffix('.lbl').write_text('PDS_VERSION_ID=PDS3\nFILE_RECORDS=57600\nRECORD_BYTES=310\nEND\n',encoding='utf-8')
    with dat.open('wb') as stream:stream.truncate(57600*310)
    def write(row=80,col=0,exposure=10,rate=0,error=0.1,coords=None):
        record=bytearray(310)
        record[:46]=b'2009-09-15T00:00:00.0002011-12-11T00:00:00.000'
        struct.pack_into('>2f',record,46,*(coords or (79.5-row,col+0.5)))
        for offset in CHANNEL_OFFSETS.values():struct.pack_into('>3f',record,offset,exposure,rate,error)
        with dat.open('r+b') as stream:stream.seek((row*360+col)*310);stream.write(record)
    write()
    return xml,write


@pytest.mark.parametrize('lat,lon,row,col',[(0,0,80,0),(79.999,0,0,0),(-79.999,359.9,159,359),
    (0,-10,80,350),(0,360,80,0),(1,1,79,1)])
def test_lend_grid_big_endian_and_zero(synthetic_lend,lat,lon,row,col):
    xml,write=synthetic_lend;write(row,col,rate=3.25)
    with LendProduct(xml) as product:result=product.sample(lat,lon,'SETN')
    assert result['value']==3.25 and result['unit'] is None
    assert result['exposure_s']==10
    assert result['statistical_error']==pytest.approx(.1)
    assert result['sampling']['record_index']==row*360+col
    assert product.stream is None


@pytest.mark.parametrize('lat',[-90,-80,80,90])
def test_lend_no_polar_extrapolation(synthetic_lend,lat):
    with LendProduct(synthetic_lend[0]) as product:result=product.sample(lat,0,'CSETN')
    assert result['value'] is None and result['reason']=='outside_declared_latitude_coverage'


@pytest.mark.parametrize('exposure,rate,error,status,reason',[(0,-1,-1,'missing','non_positive_exposure'),
    (10,1,-1,'invalid','negative_statistical_error'),(10,float('nan'),1,'missing','non_finite'),
    (float('inf'),1,1,'missing','non_finite'),(10,0,.1,'valid',None),(10,-.1,.1,'valid',None)])
def test_lend_missing_and_negative_background_values(synthetic_lend,exposure,rate,error,status,reason):
    xml,write=synthetic_lend;write(exposure=exposure,rate=rate,error=error)
    with LendProduct(xml) as product:r=product.sample(0,0,'SETN')
    assert r['status']==status
    if reason:assert reason in r['reason'] and r['value'] is None
    else:assert r['value']==pytest.approx(rate)
    json.dumps(r,allow_nan=False)


def test_lend_rejects_corrupt_coordinates_and_releases(synthetic_lend):
    xml,write=synthetic_lend;write(coords=(1,2))
    product=LendProduct(xml)
    with pytest.raises(ValueError,match='Coordenadas'):
        with product:product.sample(0,0,'SETN')
    assert product.stream is None
    with pytest.raises(RuntimeError):product.sample(0,0,'SETN')


def test_lend_only_one_record_read_per_sample(synthetic_lend):
    xml,_=synthetic_lend
    with LendProduct(xml) as product:
        original=product.stream
        calls=[]
        class OneRecord:
            def seek(self,index):calls.append(('seek',index));return original.seek(index)
            def read(self,size):assert size==310;calls.append(('read',size));return original.read(size)
            def close(self):original.close()
        product.stream=OneRecord()
        assert product.sample(0,0,'SETN')['value']==0
    assert calls==[('seek',80*360*310),('read',310)]


def test_collection_and_csv_keep_products_channels_and_raw_missing(synthetic_lend):
    xml,write=synthetic_lend
    with LendProduct(xml) as product:
        collection=LendCollection([(product,['SETN','CSETN'])])
        first=collection.sample(0,0);second=collection.sample(0,0)
        assert first==second
    doc={'schema_version':'1.0.0','sites':[{'id':'test','requested_coordinates':{'latitude_deg':0,'longitude_deg':0},'measurements':{'lend_neutron_indicator':first}}]}
    rows=list(csv.DictReader(io.StringIO(render_csv(doc,source_json_file='test.json',source_json_sha256='hash',profile='lend'))))
    assert len(rows)==2 and {r['channel'] for r in rows}=={'SETN','CSETN'}
    assert all(r['unit']=='' and float(r['value'])==0 and r['period_start']=='2009-09-15T00:00:00Z' for r in rows)
    assert first['available'] is False and first['value'] is None  # nunca ofrece un escalar ficticio
    assert first['has_available_observations'] is True


@pytest.mark.parametrize('corruption',['endian','size','coordinate','time'])
def test_lend_rejects_corrupt_metadata_or_record(synthetic_lend,corruption):
    xml,write=synthetic_lend
    if corruption=='endian':
        xml.write_text(xml.read_text().replace('IEEE754MSBSingle','IEEE754LSBSingle'),encoding='utf-8')
        with pytest.raises(ValueError):LendProduct(xml)
    elif corruption=='size':
        with xml.with_suffix('.dat').open('r+b') as stream:stream.truncate(310)
        with pytest.raises(ValueError):LendProduct(xml)
    else:
        with xml.with_suffix('.dat').open('r+b') as stream:
            stream.seek(80*360*310+(46 if corruption=='coordinate' else 0))
            stream.write(struct.pack('>f',999) if corruption=='coordinate' else b'not-a-valid-UTC-time....')
        with LendProduct(xml) as product:
            with pytest.raises(ValueError):product.sample(0,0,'SETN')


@pytest.mark.local_data
@pytest.mark.parametrize('date',['20090915','20111211'])
@pytest.mark.parametrize('channel',['SETN','CSETN'])
def test_real_lend_against_independent_binary(data_root,date,channel):
    xml=data_root/'lend'/f'lend_rdr_alde_{date}.xml'
    if not xml.exists():pytest.skip('Originales NASA no incluidos en Git')
    with LendProduct(xml) as product,xml.with_suffix('.dat').open('rb') as stream:
        for lat,lon in [(0,0),(79.5,.5),(-79.5,359.5)]:
            row=int(80-lat);col=int(lon%360)
            stream.seek((row*360+col)*310);record=stream.read(310)
            # Oráculo con offsets explícitos, sin CHANNEL_OFFSETS del lector.
            offset=70 if channel=='SETN' else 106
            exposure,rate,error=struct.unpack_from('>fff',record,offset)
            result=product.sample(lat,lon,channel)
            assert result['raw_exposure_s']==exposure and result['raw_value']==rate
            assert result['raw_statistical_error']==error
            assert struct.unpack_from('>ff',record,46)==(result['sampling']['center_latitude_deg'],result['sampling']['center_longitude_deg_east'])
            if exposure<=0:assert result['value'] is None
            else:assert result['value']==rate and result['statistical_error']==error


def test_published_auxiliary_csv_matches_every_observation(repo_root,tmp_path):
    from lunar_data.csv_export import export_csv
    source=repo_root/'data/moon/lola_measurements.example.json'
    output=tmp_path/'lend.csv'
    export_csv(source,output,'lend')
    assert output.read_bytes()==(repo_root/'data/moon/lend_observations.example.csv').read_bytes()
    with output.open(encoding='utf-8',newline='') as stream:rows=list(csv.DictReader(stream))
    document=json.loads(source.read_bytes())
    expected=[(site,item) for site in document['sites'] for item in site['measurements']['lend_neutron_indicator']['observations']]
    assert len(rows)==len(expected)==8
    for row,(site,item) in zip(rows,expected):
        assert row['site_id']==site['id'] and row['channel']==item['channel']
        assert row['product_id']==item['product_id']
        assert row['period_start']==item['period']['start'] and row['period_stop']==item['period']['stop']
        assert row['unit']=='' and row['unit_status']=='not_declared_in_product_label'
        for key in ['value','statistical_error','exposure_s','raw_value','raw_statistical_error','raw_exposure_s']:
            assert row[key]==('' if item[key] is None else str(item[key]))
        assert row['status']==item['status'] and row['reason']==(item['reason'] or '')


@pytest.mark.parametrize('change',[{'available':'false'},{'available':False,'value':1},
                                 {'available':True,'value':None}])
def test_auxiliary_csv_rejects_contradictory_availability(repo_root,change):
    document=json.loads((repo_root/'data/moon/lola_measurements.example.json').read_bytes())
    document['sites'][0]['measurements']['lend_neutron_indicator']['observations'][0].update(change)
    with pytest.raises(ValueError):
        render_csv(document,source_json_file='input.json',source_json_sha256='hash',profile='lend')
