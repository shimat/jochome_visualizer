import functools
import hashlib
import more_itertools
import pandas as pd
import pydantic_yaml
import streamlit as st
import shapely
import zipfile
from os.path import splitext
from pathlib import Path
from pydantic import BaseModel
from xml.etree import ElementTree

# https://tm23forest.com/contents/python-jpgis-gml-dem-geotiff
NAMESPACES = {
    "gml": "http://www.opengis.net/gml",
    "fme": "http://www.safe.com/gml/fme",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "xlink": "http://www.w3.org/1999/xlink"
}


@st.cache_resource
def load_data_from_gml_zip(file_name: str) -> pd.DataFrame:
    with zipfile.ZipFile(file_name, 'r') as zf:
        gml_file_name = more_itertools.first_true(zf.namelist(), pred=lambda f: splitext(f)[1] == ".gml")
        with zf.open(gml_file_name, 'r') as file:
            tree = ElementTree.parse(file)
            return load_data(tree)


def load_data(tree: ElementTree) -> pd.DataFrame:
    # root = tree.getroot()

    # bounded_by = tree.find("gml:boundedBy", NAMESPACES)
    # st.write(bounded_by)

    prefecture_names: list[str] = []
    city_names: list[str] = []
    town_names: list[str] = []
    addresses: list[str] = []
    lonlat_lists: list[list[list[list[float]]]] = []

    for feature_member in tree.findall("gml:featureMember", NAMESPACES):
        elem = feature_member[0]
        prefecture_names.append(elem.find("fme:PREF_NAME", NAMESPACES).text)
        city_name = elem.find("fme:CITY_NAME", NAMESPACES).text
        town_name = elem.find("fme:S_NAME", NAMESPACES).text
        city_names.append(city_name)
        town_names.append(town_name)
        addresses.append(f"{city_name} {town_name}")

        pos_list_elem = elem.find("gml:surfaceProperty//gml:Surface//gml:PolygonPatch//gml:exterior//gml:LinearRing//gml:posList", NAMESPACES)
        pos_list = [float(v) for v in pos_list_elem.text.split(" ")]
        lonlat_list = [[[pos_list[i*2+1], pos_list[i*2]] for i in range(len(pos_list) // 2)]]
        lonlat_lists.append(lonlat_list)

    data = {
        "prefecture_name": prefecture_names,
        "city_name": city_names,
        "town_name": town_names,
        "address": addresses,
        "lonlat_coordinates": lonlat_lists,
    }
    return pd.DataFrame(
        data=data,
        columns=data.keys()
    )


def mod_data(df: pd.DataFrame) -> pd.DataFrame:

    df = df[df["town_name"].str.contains("条")].copy()

    df["town_group"] = df["town_name"].apply(lambda x: x.split("条")[0]+"条")

    def merge_coordinates(group: pd.DataFrame):
        polygons = [shapely.geometry.Polygon(c[0])
                    for c in group["lonlat_coordinates"].values]
        if not polygons:
            return []
        merged_polygon = functools.reduce(lambda r, s: r.union(s), polygons[1:], polygons[0])
        if merged_polygon.geom_type == "Polygon":
            return [list(merged_polygon.exterior.coords)]
        elif merged_polygon.geom_type == "MultiPolygon":
            return [list(p.exterior.coords) for p in merged_polygon.geoms]
        else:
            raise

    new_data = {
        "prefecture_name": [],
        "city_name": [],
        "town_group": [],
        "lonlat_coordinates": [],
        "fill_color": []
    }
    for group_name, group_df in df.groupby("town_group"):
        prefecture_name = group_df.iloc[0]["prefecture_name"]
        city_name = ",".join(set(group_df["city_name"].values))
        md5int = int.from_bytes(hashlib.md5(group_name.encode()).digest())
        b = md5int & 0xFF
        g = (md5int >> 8) & 0xFF
        r = (md5int >> 16) & 0xFF

        coords = merge_coordinates(group_df)
        if len(coords) > 1:
            group_name += " (飛び地あり)"
        for c in coords:
            new_data["prefecture_name"].append(prefecture_name)
            new_data["city_name"].append(city_name)
            new_data["town_group"].append(group_name)
            new_data["lonlat_coordinates"].append(c)
            new_data["fill_color"].append([r, g, b, 128])
    
    new_df = pd.DataFrame(
        data=new_data,
        columns=new_data.keys())
    return new_df


class ViewState(BaseModel):
    latitude: float
    longitude: float
    zoom: float


class AllCitiesViewStates(BaseModel):
    cities: dict[str, ViewState]


def load_city_view_states() -> AllCitiesViewStates:
    path = Path("cities.yaml")
    y = path.read_text(encoding="utf-8-sig")
    return pydantic_yaml.parse_yaml_raw_as(AllCitiesViewStates, y)
