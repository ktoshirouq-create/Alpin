"""Checks that anything you type or choose is never overwritten by a later choice."""
from playwright.sync_api import sync_playwright
from harness import page, new_store, seed_plans

def run():
    issues = []
    store = new_store()
    with sync_playwright() as p:
        b, pg, errs = page(p, store)
        pg.click('#bnav [data-view=history]'); pg.wait_for_timeout(600)

        # --- the plan sheet ---
        pg.click('[data-act=plannew]'); pg.wait_for_timeout(350)
        pg.click('[data-pa=Hike]'); pg.wait_for_timeout(200)
        pg.click('.titlesec summary'); pg.wait_for_timeout(150)
        for field, value in [('minutes','300'), ('title','My own title'), ('km','12'), ('detail','Rjukan'), ('start','11:00')]:
            pg.fill(f'#planfrm [name={field}]', value)
            pg.dispatch_event(f'#planfrm [name={field}]', 'input'); pg.wait_for_timeout(120)
            pg.click('#paKinds [data-kind=peak]'); pg.wait_for_timeout(220)
            got = pg.input_value(f'#planfrm [name={field}]')
            if got != value: issues.append(f'plan sheet: {field} you set was rewritten by choosing a kind ({got})')
        pg.fill('#planfrm [name=minutes]','300'); pg.dispatch_event('#planfrm [name=minutes]','input')
        pg.click('[data-pa=Climbing]'); pg.wait_for_timeout(220)
        if pg.input_value('#planfrm [name=minutes]') != '300':
            issues.append('plan sheet: minutes rewritten by switching activity')
        pg.fill('#planfrm [name=start]','11:00'); pg.dispatch_event('#planfrm [name=start]','input')
        pg.click('#durChips [data-min="480"]'); pg.wait_for_timeout(200)
        if pg.input_value('#planfrm [name=start]') != '11:00':
            issues.append('plan sheet: start time rewritten by a duration chip')
        pg.click('#planfrm button[value=cancel]'); pg.wait_for_timeout(250)

        # --- the editor ---
        seed_plans(pg, [{'id':'e1','date':'2026-10-07','start':'11:00','minutes':120,
                         'title':'Hike · day hike · 17 km','tab':'Hike','items':[],'status':'planned'}])
        pg.wait_for_timeout(300); pg.click('.cd[data-d="2026-10-07"]'); pg.wait_for_timeout(400)
        pg.click('.prow .pmain'); pg.wait_for_timeout(350)
        pg.fill('#editplanfrm [name=title]','My hike title'); pg.dispatch_event('#editplanfrm [name=title]','input')
        pg.click('#epTypes [data-type=Hike]'); pg.wait_for_timeout(220)
        if pg.input_value('#editplanfrm [name=title]') != 'My hike title':
            issues.append('editor: a title you wrote was rewritten by changing type')
        pg.fill('#editplanfrm [name=minutes]','95'); pg.dispatch_event('#editplanfrm [name=minutes]','input')
        pg.click('#epTypes [data-type=Climbing]'); pg.wait_for_timeout(220)
        if pg.input_value('#editplanfrm [name=minutes]') != '95':
            issues.append('editor: minutes you set were rewritten by changing type')
        if pg.input_value('#editplanfrm [name=start]') != '11:00':
            issues.append('editor: the start time moved on its own')
        pg.fill('#editplanfrm [name=date]','2026-10-09'); pg.click('#epChips [data-min="120"]'); pg.wait_for_timeout(200)
        if pg.input_value('#editplanfrm [name=date]') != '2026-10-09':
            issues.append('editor: the day changed on its own')
        issues += ['JS ERROR ' + e for e in errs]
        b.close()
    print('\n'.join(issues) if issues else 'nothing you set gets overwritten')
    print('---', len(issues), 'issues')
    return not issues

if __name__ == '__main__':
    import sys; sys.exit(0 if run() else 1)
