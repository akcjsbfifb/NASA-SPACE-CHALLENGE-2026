from pathlib import Path
import struct

import pytest

from lunar_data.lunar_prospector import LunarProspectorHydrogen, validate_binary_against_ascii


@pytest.fixture
def hydrogen_files(tmp_path):
    binary, reference = tmp_path / "hydrogenhd.dat", tmp_path / "hydrogenhd.txt"
    header = b'# Hydrogen_halfdeg\n# 259200 binned values; H ppm by weight\n'
    with binary.open("wb") as stream:
        stream.truncate(720 * 360 * 2)
    with reference.open("wb") as stream:
        stream.write(header)
        stream.truncate(len(header) + 259200 * 55)
    def write(row, column, raw=523, ascii_value="52.353"):
        bounds = (-90 + row / 2, -89.5 + row / 2, -180 + column / 2, -179.5 + column / 2)
        line = (','.join(map(str, bounds)) + ',' + ascii_value).ljust(54).encode('ascii') + b'\n'
        assert len(line) == 55
        index = row * 720 + column
        with binary.open('r+b') as stream:
            stream.seek(index * 2); stream.write(struct.pack('>h', raw))
        with reference.open('r+b') as stream:
            stream.seek(len(header) + index * 55); stream.write(line)
    write(0, 0); write(359, 719)
    return binary, reference, write


@pytest.mark.parametrize('lat,lon,row,column', [(0,0,180,360),(-85,-10,10,340),
    (45,90,270,540),(-45,-90,90,180),(0,180,180,0),(0,-180,180,0),
    (0,360,180,360),(89.999,179.999,359,719),(-89.999,-179.999,0,0),
    (.25,.25,180,360),(-.5,-.5,179,359)])
def test_coordinates_orientation_and_scaled_values(hydrogen_files, lat, lon, row, column):
    binary, reference, write = hydrogen_files
    write(row, column)
    with LunarProspectorHydrogen(binary, reference) as product:
        result = product.sample(lat, lon)
    assert result['value'] == 52.3 and result['unit'] == 'ppm'
    assert result['raw_value'] == 523 and result['ascii_reference_value_ppm'] == 52.353
    assert (result['sampling']['row'], result['sampling']['column']) == (row,column)
    assert result['sampling']['center_latitude_deg'] == -89.75 + row / 2
    assert product.binary is None and product.ascii is None


@pytest.mark.parametrize('raw,token,status,value', [(0,'**********','missing',None),
    (0,'0.0000','valid',0.0),(0,'0.034','valid',0.0),
    (-114,'-11.414','invalid',None),(0,'-0.034','invalid',None),
    (523,'99.1','invalid',None)])
def test_zero_missing_negative_and_mismatched_estimates(hydrogen_files,raw,token,status,value):
    binary, reference, write = hydrogen_files; write(180,360,raw,token)
    with LunarProspectorHydrogen(binary,reference) as product: result=product.sample(0,0)
    assert result['value']==value and result['status']==status
    assert result['available']==(status=='valid')
    assert result['raw_value']==raw


@pytest.mark.parametrize('latitude',[-90,90])
def test_exact_poles_are_not_arbitrary_longitude_samples(hydrogen_files,latitude):
    with LunarProspectorHydrogen(*hydrogen_files[:2]) as product: result=product.sample(latitude,0)
    assert result['value'] is None and result['status']=='not_sampled'
    assert 'longitude_is_degenerate' in result['reason']


def test_only_two_binary_and_one_ascii_record_read(hydrogen_files):
    binary, reference, write = hydrogen_files; write(180,360)
    with LunarProspectorHydrogen(binary,reference) as product:
        original_binary,original_ascii=product.binary,product.ascii
        reads=[]
        class Guard:
            def __init__(self,stream,length):self.stream,self.length=stream,length
            def seek(self,*args):return self.stream.seek(*args)
            def read(self,size):
                assert size==self.length;reads.append(size);return self.stream.read(size)
            def close(self):self.stream.close()
        product.binary=Guard(original_binary,2);product.ascii=Guard(original_ascii,55)
        assert product.sample(0,0)['value']==52.3
    assert reads==[2,55]
    assert original_binary.closed and original_ascii.closed


def test_incorrect_ascii_geometry_fails_and_releases_files(hydrogen_files):
    binary, reference, write = hydrogen_files; write(180,360)
    with reference.open('r+b') as stream:
        stream.seek(len(b'# Hydrogen_halfdeg\n# 259200 binned values; H ppm by weight\n')+(180*720+360)*55)
        stream.write(b'1.0,1.5,0.0,0.5,52.353'.ljust(54)+b'\n')
    product=LunarProspectorHydrogen(binary,reference)
    with pytest.raises(ValueError,match='l.mites ASCII'):
        with product:product.sample(0,0)
    assert product.binary is None and product.ascii is None


@pytest.mark.local_data
def test_all_original_cells_binary_vs_ascii(repo_root):
    folder=repo_root/'NASA-Lunar-Studies/data/raw/lunar_prospector/hydrogen'
    if not (folder/'hydrogenhd.dat').exists():pytest.skip('Originales NASA locales no incluidos en Git')
    result=validate_binary_against_ascii(folder/'hydrogenhd.dat',folder/'hydrogenhd.txt')
    assert result['cells_compared']==259200
    assert result['ascii_missing_cells']==1 and result['negative_ascii_estimates']==4180
    assert result['non_negative_ascii_cells_encoded_zero']==36
    assert result['max_absolute_binary_ascii_difference_ppm']<=.100001
    missing=next(c for c in result['special_cells'] if c['kind']=='missing')
    with LunarProspectorHydrogen(folder/'hydrogenhd.dat',folder/'hydrogenhd.txt') as product:
        for cell in result['special_cells']:
            sampled=product.sample(-89.75+cell['row']/2,-179.75+cell['column']/2)
            assert sampled['status']=={'missing':'missing','negative':'invalid','zero_valid':'valid'}[cell['kind']]


@pytest.mark.local_data
@pytest.mark.parametrize('lat,lon',[(0,0),(-85,-10),(45,90),(-45,-90),(0,180),
    (0,-180),(89.999,0),(-89.999,0),(.25,.25),(43.25,153.75)])
def test_real_coordinate_selection_against_ascii_intervals(repo_root,lat,lon):
    folder=repo_root/'NASA-Lunar-Studies/data/raw/lunar_prospector/hydrogen'
    if not (folder/'hydrogenhd.dat').exists():pytest.skip('Originales NASA locales no incluidos en Git')
    signed_lon=(lon+180)%360-180
    found=None
    with (folder/'hydrogenhd.txt').open('r',encoding='ascii') as stream:
        for line in stream:
            if line.startswith('#'):continue
            parts=line.split(',');south,north,west,east=map(float,parts[:4])
            if south<=lat<north and west<=signed_lon<east:
                found=(south,north,west,east,parts[4].strip());break
    assert found is not None
    with LunarProspectorHydrogen(folder/'hydrogenhd.dat',folder/'hydrogenhd.txt') as product:
        sampled=product.sample(lat,lon)
    assert sampled['sampling']['latitude_bounds_deg']==list(found[:2])
    assert sampled['sampling']['longitude_bounds_deg_east_signed']==list(found[2:4])
    if found[4]=='**********':assert sampled['value'] is None and sampled['status']=='missing'
    else:
        value=float(found[4]);assert abs(sampled['raw_value']/10-value)<=.100001
        assert sampled['value']==(None if value<0 else sampled['raw_value']/10)
