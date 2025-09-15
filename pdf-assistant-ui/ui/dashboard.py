
import pandas as pd
from dash import Dash, html, dcc, Input, Output
import plotly.express as px

df = pd.read_csv("pdf-assistant-ui/raw_data/epz_timesheet_demo.csv", parse_dates=["date"])
agreed = pd.read_csv("pdf-assistant-ui/raw_data/epz_agreed_hours.csv")
df["month_name"] = df["date"].dt.strftime("%b")
df["year"] = df["date"].dt.year

app = Dash(__name__)
server = app.server

def layout_controls():
    return html.Div([
        html.Div([html.Label("RIZIV/KBO nummer"),
                  dcc.Dropdown(options=[{"label":"Alle","value":"Alle"}] + [{"label":r,"value":r} for r in sorted(df["riziv_number"].unique())],
                               value="Alle", id="dd-riziv")], style={"width":"22%","display":"inline-block","padding":"0 10px"}),
        html.Div([html.Label("Naam"),
                  dcc.Dropdown(options=[{"label":"Alle","value":"Alle"}] + [{"label":n,"value":n} for n in sorted(df["psychologist_name"].unique())],
                               value="Alle", id="dd-name")], style={"width":"28%","display":"inline-block","padding":"0 10px"}),
        html.Div([html.Label("Regionaam"),
                  dcc.Dropdown(options=[{"label":"Alle","value":"Alle"}] + [{"label":r,"value":r} for r in sorted(df["region"].unique())],
                               value="Alle", id="dd-region")], style={"width":"28%","display":"inline-block","padding":"0 10px"}),
        html.Div([html.Label("Jaar"),
                  dcc.Dropdown(options=[{"label":int(y),"value":int(y)} for y in sorted(df["year"].unique())],
                               value=int(df["year"].max()), id="dd-year")], style={"width":"12%","display":"inline-block","padding":"0 10px"}),
    ])

def kpi_card(label, value):
    return html.Div([html.H4(label, style={"margin":"0"}), html.H2(value, style={"margin":"0"})],
                    style={"display":"inline-block","padding":"12px 18px","border":"1px solid #eee","borderRadius":"8px","marginRight":"12px"})

app.layout = html.Div([
    html.H1("EPZ Dashboard (demo)"),
    layout_controls(),
    html.Div(id="kpis", style={"margin":"16px 0"}),
    html.Div([dcc.Graph(id="g-uren-per-maand"), dcc.Graph(id="g-tov-overeengekomen")],
             style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"16px"}),
    html.Div([dcc.Graph(id="g-verdeling-functie"), dcc.Graph(id="g-zorgplaats"), dcc.Graph(id="g-clienttype")],
             style={"display":"grid","gridTemplateColumns":"1fr 1fr 1fr","gap":"16px","marginTop":"16px"}),
], style={"fontFamily":"Segoe UI, Arial"})

def filter_df(year, region, name, riziv):
    d = df[df["year"]==year]
    if region != "Alle":
        d = d[d["region"]==region]
    if name != "Alle":
        d = d[d["psychologist_name"]==name]
    if riziv != "Alle":
        d = d[d["riziv_number"]==riziv]
    return d

@app.callback(
    Output("kpis","children"),
    Output("g-uren-per-maand","figure"),
    Output("g-tov-overeengekomen","figure"),
    Output("g-verdeling-functie","figure"),
    Output("g-zorgplaats","figure"),
    Output("g-clienttype","figure"),
    Input("dd-year","value"), Input("dd-region","value"), Input("dd-name","value"), Input("dd-riziv","value"),
)
def update(year, region, name, riziv):
    d = filter_df(year, region, name, riziv)
    total_hours = d["hours"].sum()
    max_functie3 = int((d["function"]=="functie3").sum())
    functie3_pct = (d[d["function"]=="functie3"]["hours"].sum()/total_hours*100) if total_hours>0 else 0
    last_update = d["date"].max().strftime("%-d %B %Y") if len(d)>0 else "-"
    kpis = [kpi_card("Laatste status update", last_update),
            kpi_card("Totaal uren", f"{int(total_hours)}"),
            kpi_card("Max functie 3", f"{max_functie3}"),
            kpi_card("Functie 3 %", f"{functie3_pct:.0f}%")]
    hours_month = d.groupby(["month","function"])["hours"].sum().reset_index()
    import plotly.express as px
    fig1 = px.bar(hours_month, x="month", y="hours", color="function", title="Gepresteerde uren per maand (stacked)")
    if region != "Alle":
        agreed_val = agreed[(agreed["year"]==year) & (agreed["region"]==region)]["agreed_hours"].sum()
    else:
        agreed_val = agreed[agreed["year"]==year]["agreed_hours"].sum()
    comp = pd.DataFrame({"type":["Gepresteerd","Overeengekomen"], "uren":[total_hours, agreed_val]})
    fig2 = px.bar(comp, x="type", y="uren", title="T.o.v. overeengekomen")
    fig3 = px.bar(d.groupby("function")["hours"].sum().reset_index(), x="function", y="hours", title="Naar functie")
    fig4 = px.bar(d.groupby("care_place")["hours"].sum().reset_index(), x="care_place", y="hours", title="Naar zorgplaats")
    fig5 = px.bar(d.groupby("client_type")["hours"].sum().reset_index(), x="client_type", y="hours", title="Naar clienttype")
    return kpis, fig1, fig2, fig3, fig4, fig5

if __name__ == "__main__":
    app.run_server(debug=True)
