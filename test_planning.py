"""Planning: the sheet, kinds and fields, the editor, trips, week planning, selection."""
from playwright.sync_api import sync_playwright
from harness import page, Checks, new_store, gotab, openrow

def run():
    c = Checks('planning')
    store = new_store()
    with sync_playwright() as p:
        b, pg, errs = page(p, store)
        pg.click('#bnav [data-view=history]'); pg.wait_for_timeout(600)

        # --- the plan sheet ---
        pg.click('[data-act=plannew]'); pg.wait_for_timeout(350)
        c.ok('six activities', pg.locator('.pacard').count() == 6)
        c.ok('it points at trips first', 'more than one day' in pg.inner_text('.tripline'))
        counts = {}
        for t in ['Run','Climbing','Bouldering','Ice climbing','Hike','Other']:
            pg.click(f'[data-pa="{t}"]'); pg.wait_for_timeout(200)
            counts[t] = pg.locator('#paKinds .tchip').count()
        c.ok('every activity has real options', min(counts.values()) >= 4, counts)
        c.ok('kind chip matches the activity colour', pg.evaluate(
            "()=>{const k=document.querySelector('#paKinds .tchip.on'),a=document.querySelector('.pacard.on');"
            "return getComputedStyle(k).borderColor===getComputedStyle(a).borderColor}"))

        pg.click('[data-pa=Hike]'); pg.wait_for_timeout(200)
        c.ok('a hike asks distance and ascent', pg.is_visible('#paKmLab') and pg.is_visible('#paUpLab'))
        pg.fill('#planfrm [name=km]','17'); pg.dispatch_event('#planfrm [name=km]','input')
        pg.fill('#planfrm [name=up]','1700'); pg.dispatch_event('#planfrm [name=up]','input'); pg.wait_for_timeout(250)
        c.ok('it works out the length', pg.input_value('#planfrm [name=minutes]') == '390',
             pg.input_value('#planfrm [name=minutes]'))
        c.ok('and says so', '6.5 h' in pg.inner_text('#durHint'), pg.inner_text('#durHint'))
        pg.click('#durChips [data-min="120"]'); pg.wait_for_timeout(250)
        c.ok('it flags a length that disagrees', 'looks short' in pg.inner_text('#durHint'))
        pg.click('[data-act=useEst]'); pg.wait_for_timeout(250)
        c.ok('one tap to accept', pg.input_value('#planfrm [name=minutes]') == '390')
        c.ok('the title carries the numbers', '17 km' in pg.input_value('#planfrm [name=title]')
             and '1700 m up' in pg.input_value('#planfrm [name=title]'), pg.input_value('#planfrm [name=title]'))
        c.ok('overnight suggests a trip', (pg.click('#paKinds [data-kind=overnight]'), pg.wait_for_timeout(200),
             pg.is_visible('#paNudge'))[-1])
        pg.click('#paKinds [data-kind=pack]'); pg.wait_for_timeout(200)

        # nothing you set gets overwritten
        pg.fill('#planfrm [name=start]','11:00'); pg.dispatch_event('#planfrm [name=start]','input')
        pg.click('#durChips [data-min="480"]'); pg.wait_for_timeout(200)
        c.ok('a start you chose survives Full day', pg.input_value('#planfrm [name=start]') == '11:00')
        pg.fill('#planfrm [name=minutes]','300'); pg.dispatch_event('#planfrm [name=minutes]','input')
        pg.click('#paKinds [data-kind=peak]'); pg.wait_for_timeout(200)
        c.ok('a length you typed survives a new kind', pg.input_value('#planfrm [name=minutes]') == '300')

        pg.fill('#planfrm [name=detail]','Gaustatoppen'); pg.dispatch_event('#planfrm [name=detail]','input')
        pg.fill('#planfrm [name=date]','2026-10-20'); pg.click('#planfrm button[value=save]'); pg.wait_for_timeout(900)
        saved = [x for x in store['plans'] if x['date'] == '2026-10-20']
        c.ok('it reaches the calendar', len(saved) == 1 and saved[0]['minutes'] == 300
             and saved[0]['start'] == '11:00', saved)
        c.ok('the place is remembered', (pg.click('[data-act=plannew]'), pg.wait_for_timeout(300),
             pg.click('[data-pa=Hike]'), pg.wait_for_timeout(200),
             'Gaustatoppen' in pg.inner_text('#paPlaces'))[-1])
        pg.click('#planfrm button[value=cancel]'); pg.wait_for_timeout(200)

        # --- training lives inside each discipline ---
        pg.click('[data-act=plannew]'); pg.wait_for_timeout(350)
        pg.click('[data-pa="Ice climbing"]'); pg.wait_for_timeout(300)
        out = pg.eval_on_selector_all('#paKinds .tchip:not(.train):not(.sm)', 'n=>n.map(x=>x.textContent)')
        tr = pg.eval_on_selector_all('#paKinds .tchip.train', 'n=>n.map(x=>x.textContent)')
        c.ok('ice offers days out and ice training',
             'Ice cragging' in out and any('Tools and grip' in t for t in tr), (out, tr))
        pg.click('[data-pa=Hike]'); pg.wait_for_timeout(250)
        trh = pg.eval_on_selector_all('#paKinds .tchip.train', 'n=>n.map(x=>x.textContent)')
        c.ok('a hike trains with Nepal strength', any('Nepal' in t for t in trh), trh)
        pg.click('[data-pa=Climbing]'); pg.wait_for_timeout(250)
        trc = pg.eval_on_selector_all('#paKinds .tchip.train', 'n=>n.map(x=>x.textContent)')
        c.ok('climbing trains fingers and pulling',
             any('Fingers' in t for t in trc) and any('Pull' in t for t in trc), trc)
        c.ok('and single exercises are there too', pg.locator('.pickex.single').count() == 1)
        pg.click('.pickex.single summary'); pg.wait_for_timeout(250)
        names = pg.eval_on_selector_all('.tchip.sm', 'n=>n.map(x=>x.textContent)')
        c.ok('the single list sticks to that discipline',
             any('Hangboard' in n for n in names) and not any('Step-ups' in n for n in names), names[:6])
        pg.click('[data-pa="Ice climbing"]'); pg.wait_for_timeout(250)
        pg.click('#paKinds .tchip.train >> nth=0'); pg.wait_for_timeout(300)
        c.ok('picking training names the session and times it',
             pg.input_value('#planfrm [name=title]') == 'Ice · Tools and grip'
             and int(pg.input_value('#planfrm [name=minutes]')) >= 10,
             (pg.input_value('#planfrm [name=title]'), pg.input_value('#planfrm [name=minutes]')))
        pg.fill('#planfrm [name=date]', '2026-10-12')
        pg.click('#planfrm button[value=save]'); pg.wait_for_timeout(1100)
        tr2 = [x for x in store['plans'] if x['date'] == '2026-10-12']
        c.ok('it lands in the calendar with its exercises',
             len(tr2) == 1 and tr2[0]['tab'] == 'Ice' and len(tr2[0]['items']) >= 1, tr2)
        pg.click('.cd[data-d="2026-10-12"]'); pg.wait_for_timeout(400)
        c.ok('and can be started from the day', pg.locator('.prow [data-act=pstart]').count() == 1)
        pg.click('.prow [data-act=pstart]'); pg.wait_for_timeout(350)
        c.ok('the timer runs those exercises', pg.evaluate('F.open') and pg.evaluate('F.src.length') >= 1)
        pg.click('#faX'); pg.wait_for_timeout(200)
        if pg.locator('[data-act=discard]').count(): pg.click('[data-act=discard]')

        # --- the editor ---
        pg.click('.cd[data-d="2026-10-20"]'); pg.wait_for_timeout(400)
        pg.click('.prow .pmain'); pg.wait_for_timeout(350)
        c.ok('type chips, no dropdown', pg.locator('#epTypes .tchip').count() >= 5
             and pg.get_attribute('#epTypes .tchip.on', 'data-type') == 'Hike')
        pg.fill('#editplanfrm [name=title]','My own words'); pg.dispatch_event('#editplanfrm [name=title]','input')
        pg.click('#epTypes [data-type=Bouldering]'); pg.wait_for_timeout(250)
        c.ok('a title you wrote is kept', pg.input_value('#editplanfrm [name=title]') == 'My own words')
        c.ok('the length follows the new type', pg.input_value('#editplanfrm [name=minutes]') == '180')
        pg.click('#epTypes [data-type=Run]'); pg.wait_for_timeout(250)
        c.ok('switching to Run opens its fields', pg.is_visible('#epRun'))
        pg.click('#editplanfrm button[value=save]'); pg.wait_for_timeout(1200)
        moved = [x for x in store['plans'] if x['tab'] == 'Run']
        c.ok('the type is saved', len(moved) == 1, [ (x['date'],x['tab']) for x in store['plans'] ])

        # --- trips ---
        pg.click('[data-act=tripnew]'); pg.wait_for_timeout(300)
        pg.fill('#tripnewfrm [name=name]','Rjukan'); pg.fill('#tripnewfrm [name=start]','2026-10-27')
        pg.fill('#tripnewfrm [name=end]','2026-10-28'); pg.click('#trKinds [data-trkind=Hike]')
        pg.click('#tripnewfrm button[value=save]'); pg.wait_for_timeout(500)
        c.ok('the trip editor opens on day one', pg.evaluate("document.getElementById('tripdlg').open")
             and pg.locator('#trRail .day').count() == 3)
        pg.click('.tl .ghost'); pg.wait_for_timeout(500)
        c.ok('adding lands on that day', pg.input_value('#planfrm [name=date]') == '2026-10-27')
        pg.click('[data-pa=Hike]'); pg.fill('#planfrm [name=start]','09:00')
        pg.click('#planfrm button[value=save]'); pg.wait_for_timeout(900)
        c.ok('and comes back into the trip', pg.evaluate("document.getElementById('tripdlg').open")
             and pg.locator('.trpanel .tl .ev').count() == 1)
        c.ok('the session belongs to the trip', pg.evaluate("Object.keys(S.tripOf).length") == 1)
        pg.click('#tripfrm button[value=cancel]'); pg.wait_for_timeout(300)
        pg.click('.cd[data-d="2026-10-27"]'); pg.wait_for_timeout(300)
        c.ok('the day heading carries the trip', 'day 1 of 2' in pg.inner_text('.dayhead.trip'))
        c.ok('trip days are washed in the grid', pg.locator('.cd.trip').count() == 2)
        c.ok('the month stays centred, with Today on the line above',
             pg.evaluate("""()=>{const h=document.querySelector('.calhead'),t=document.querySelector('.todaybtn');
               if(!t||h.contains(t))return false;
               const r=h.querySelector('h2').getBoundingClientRect(),w=h.getBoundingClientRect();
               return Math.abs((r.left+r.right)/2-(w.left+w.right)/2)<12}"""))
        c.ok('and count as away', pg.evaluate("tripDays().has('2026-10-27')&&tripDays().has('2026-10-28')"))
        c.ok('one line per session', pg.locator('.prow').count() == 1)

        # --- week planning ---
        pg.click('[data-act=runweek]'); pg.wait_for_timeout(900)
        t0 = pg.inner_text('#rwTitle')
        c.ok('the running week opens on the week you are looking at',
             'Oct 26' in pg.inner_text('#rwSub'), pg.inner_text('#rwSub'))
        pg.click('[data-rw=next]'); pg.wait_for_timeout(800)
        c.ok('and steps to another week', pg.inner_text('#rwTitle') != t0)
        pg.click('#runweekfrm button[value=cancel]'); pg.wait_for_timeout(250)
        pg.click('[data-act=weekbuild]'); pg.wait_for_timeout(450)
        c.ok('build a week has its own switcher', pg.locator('[data-wbnav=next]').count() == 1
             and pg.locator('.wbday').count() == 7)
        pg.click('[data-wbadd="nepal|0|x:stepup"]'); pg.wait_for_timeout(200)
        c.ok('picking an exercise lands on the day', pg.locator('.wbpicked .sdrow').count() == 1)
        pg.click('#weekfrm button[value=cancel]'); pg.wait_for_timeout(250)

        # --- selecting while browsing ---
        gotab(pg, 'nepal'); pg.click('.spill.sel'); pg.wait_for_timeout(250)
        pg.click('.exrow[data-id=stepup]'); pg.click('.exrow[data-id=calf]'); pg.wait_for_timeout(200)
        c.ok('two picked, bar shows it', pg.locator('.exrow.picked').count() == 2 and '2' in pg.inner_text('#selbar'))
        gotab(pg, 'ice'); pg.click('.exrow[data-id=frontpoint]'); pg.wait_for_timeout(200)
        c.ok('selection crosses tabs', '3' in pg.inner_text('#selbar'))
        pg.click('[data-act=seladd]'); pg.wait_for_timeout(300)
        c.ok('the day sheet lists them', pg.locator('#sdList .sdrow').count() == 3)
        pg.fill('#seldayfrm [name=date]','2026-10-21'); pg.click('#seldayfrm button[value=save]'); pg.wait_for_timeout(900)
        made = [x for x in store['plans'] if x['date'] == '2026-10-21']
        c.ok('they become one session', len(made) == 1 and len(made[0]['items']) == 3, made)

        c.ok('no errors', not errs, errs)
        b.close()
    return c.report()

if __name__ == '__main__':
    import sys; sys.exit(0 if run() else 1)
