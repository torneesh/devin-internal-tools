"""3-year cost model: Buy (Power Apps) vs Hybrid (Power Apps + Devin code apps) vs Build (in-house + Devin).

Every number is an assumption; edit ASSUMPTIONS and re-run. Sources/notes in docs/COST_MODEL.md.
"""

ASSUMPTIONS = dict(
    eng_loaded_per_year=230_000,   # fully loaded US fintech engineer (published range ~$200-265K)
    eng_weeks_per_year=46,
    license_y1=250_000,            # given in brief
    license_growth=0.15,           # yearly ops-headcount growth if licensing is per-user
    pp_admin_fte=0.25,             # Power Platform admin / ALM / environment governance (Buy, Hybrid)
    devin_per_year=30_000,         # placeholder: Teams list is $40/full seat/mo + credits; Enterprise is quote-only
    new_apps_by_year=(6, 4, 0),    # 10 new apps over two years
    weeks_per_app=dict(buy=2.0, hybrid=1.25, build=1.25),  # eng-weeks incl. review, UAT, release
    migrate_existing_weeks=4.5,    # Build only: 3 existing apps x 1.5 wk, year 1
    maint_weeks_per_app_year=0.5,  # all options
    platform_build_weeks=8,        # Build only, year 1: real SSO, Postgres, deploy, monitoring, hardening
    platform_owner_fte=0.5,        # Build only, ongoing
    hosting_per_year=15_000,       # Build only
    pentest_per_year=20_000,       # Build only: extra scope for the in-house platform
    build_license_years=1,         # Build pays the licence until renewal after migration
)


def model(a):
    wk = a["eng_loaded_per_year"] / a["eng_weeks_per_year"]
    fte = a["eng_loaded_per_year"]
    out = {k: [] for k in ("buy", "hybrid", "build")}
    apps_live = 3
    for y in range(3):
        lic = a["license_y1"] * (1 + a["license_growth"]) ** y
        new = a["new_apps_by_year"][y]
        maint = apps_live * a["maint_weeks_per_app_year"] * wk
        for opt in out:
            c = new * a["weeks_per_app"][opt] * wk + maint
            if opt in ("buy", "hybrid"):
                c += lic + a["pp_admin_fte"] * fte
            if opt == "hybrid":
                c += a["devin_per_year"]
            if opt == "build":
                c += a["devin_per_year"] + a["hosting_per_year"] + a["pentest_per_year"]
                c += a["platform_owner_fte"] * fte
                if y < a["build_license_years"]:
                    c += lic + a["pp_admin_fte"] * fte
                if y == 0:
                    c += (a["platform_build_weeks"] + a["migrate_existing_weeks"]) * wk
            out[opt].append(c)
        apps_live += new
    return out


def show(title, a):
    r = model(a)
    print(f"\n{title}")
    print(f"{'option':<8}{'Y1':>10}{'Y2':>10}{'Y3':>10}{'3yr':>11}")
    for k, v in r.items():
        print(f"{k:<8}" + "".join(f"{x/1000:>9.0f}K" for x in v) + f"{sum(v)/1000:>10.0f}K")


if __name__ == "__main__":
    base = ASSUMPTIONS
    show("BASE", base)
    show("Licence flat (no user growth)", {**base, "license_growth": 0})
    show("Licence optimised to $150K (per-app/PAYG for light users)", {**base, "license_y1": 150_000})
    show("Build pessimistic (1 FTE owner, 3 wk/app, 16 wk platform)",
         {**base, "platform_owner_fte": 1.0, "weeks_per_app": {**base["weeks_per_app"], "build": 3.0},
          "platform_build_weeks": 16})
    show("Devin Enterprise at $100K/yr", {**base, "devin_per_year": 100_000})
