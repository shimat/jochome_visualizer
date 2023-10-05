import pydeck
import streamlit as st
from data_loader import load_data_from_gml_zip, mod_data, load_city_view_states
import time


st.set_page_config(page_title="条丁目の可視化")

t = time.perf_counter()
df_org = load_data_from_gml_zip("gml/経済センサス_活動調査_北海道.zip")
print(f"DataFrame Load Time = {time.perf_counter() - t}s")

city_name = st.selectbox(
    label="市区町村",
    options=(
        "札幌市",
        "旭川市",
        "帯広市",
        "北見市",
        "岩見沢市",
        "石狩市",
    ),
)

t = time.perf_counter()
view_states = load_city_view_states()
print(f"AreaData Load Time = {time.perf_counter() - t}s")

t = time.perf_counter()
df_target = df_org[df_org["city_name"].str.contains(city_name, na=False)].copy()
df_mod = mod_data(df_target)
view_state = view_states.cities[city_name]
print(f"DataFrame Mod Time = {time.perf_counter() - t}s")


df_map = {"条ごとに分類": df_mod, "全町名": df_target}
tabs = dict(zip(df_map.keys(), st.tabs(df_map.keys())))

for name, df in df_map.items():
    with tabs[name]:
        get_fill_color = [0, 0, 0, 64] if name == "全町名" else "fill_color"
        polygon_layer = pydeck.Layer(
            "PolygonLayer",
            df,
            stroked=True,
            filled=True,
            extruded=False,
            wireframe=True,
            line_width_scale=10,
            line_width_min_pixels=1,
            get_polygon="lonlat_coordinates",
            get_line_color=[255, 255, 255],
            get_fill_color=get_fill_color,
            highlight_color=[0, 0, 255, 128],
            auto_highlight=True,
            pickable=True,
        )
        tooltip = "{address}" if name == "全町名" else "{town_group}"
        deck = pydeck.Deck(
            layers=(polygon_layer,),
            initial_view_state=pydeck.ViewState(
                latitude=view_state.latitude,
                longitude=view_state.longitude,
                zoom=view_state.zoom,
                max_zoom=16,
                pitch=0,
                bearing=0,
            ),
            tooltip={"text": tooltip},
        )
        st.pydeck_chart(deck)

        address_label = "住所"
        st.dataframe(
            df,
            hide_index=True,
            column_config={
                "prefecture_name": st.column_config.TextColumn("都道府県", width="small"),
                "address": address_label,
                "sub_addresses": st.column_config.ListColumn("含む町名"),
                "lonlat_coordinates": None,
                "city_name": None,
            },
        )


st.markdown(
    """
-----

利用データ:
+ [e-Stat 統計で見る日本](https://www.e-stat.go.jp/gis/statmap-search?page=1&type=2&aggregateUnitForBoundary=A&toukeiCode=00200553&toukeiYear=2016&serveyId=A002005532016&coordsys=1&format=gml&datum=2011): 経済センサス－活動調査（総務省・経済産業省）/ 2016年 / 小地域（町丁・大字）（JGD2011）
""",  # noqa: E501
    unsafe_allow_html=True,
)
