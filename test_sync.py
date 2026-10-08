"""Sync: connecting, the offline queue, duplicates, backup and restore."""
from playwright.sync_api import sync_playwright
from harness import page, Checks, new_store, make_handler, SYNC, URL, gotab, openrow

def run():
    c = Checks('sync')
    store = new_store()
    with sync_playwright() as p:
        # --- a fresh browser is honest about not being connected ---
        b, pg, errs = page(p, store, connected=False)
        c.ok('says it is not connected', 'isn' in pg.inner_text('main') and 'connected' in pg.inner_text('main'))
        c.ok('history still works on the phone', pg.evaluate("Array.isArray(localLog())"))
        b.close()

        # --- connected: logging and planning reach the sheet ---
        b, pg, errs = page(p, store)
        gotab(pg, 'ice'); openrow(pg, 'toolhang')
        pg.click('.ex.open [data-act=logdone]'); pg.wait_for_timeout(300)
        pg.evaluate("flushQueue()"); pg.wait_for_timeout(1200)
        c.ok('a logged exercise reaches the sheet', len(store['log']) == 1, store['log'])
        c.ok('and shows as done', pg.locator('.ex.open.donecard, .exrow.done').count() >= 1)
        pg.click('#bnav [data-view=history]'); pg.wait_for_timeout(600)
        c.ok('the calendar says it synced', 'ynced' in pg.inner_text('#syncline'), pg.inner_text('#syncline'))

        # --- duplicates ---
        dup = {'id':'d1','date':'2026-10-20','start':'12:00','minutes':35,'title':'Easy run · 4.5 km',
               'tab':'Run','items':[],'status':'planned'}
        store['plans'] = [dict(dup), dict(dup, id='d2'), dict(dup, id='d3')]
        pg.evaluate("pullPlans()"); pg.wait_for_timeout(900)
        c.ok('duplicates are spotted', pg.locator('.adjcard.hard').count() == 1
             and '2 duplicate' in pg.inner_text('.adjcard.hard'), pg.inner_text('.adjcard.hard')[:60]
             if pg.locator('.adjcard.hard').count() else 'none')
        pg.click('[data-act=dupfix]'); pg.wait_for_timeout(200); pg.click('#askYes'); pg.wait_for_timeout(1200)
        c.ok('and removed from the calendar', len(store['plans']) == 1, [x['id'] for x in store['plans']])
        c.ok('the warning clears', pg.locator('.adjcard.hard').count() == 0)

        # --- the offline queue ---
        pg.context.set_offline(True)
        pg.evaluate("""()=>{const id='off1';setPlans(plansCache().concat([{id,date:'2026-10-22',start:'09:00',
          minutes:60,title:'Climbing',tab:'Climbing',items:[],status:'planned',pending:true}]));
          enqueue({op:'plan',plan:{id,date:'2026-10-22',start:'09:00',minutes:60,title:'Climbing',tab:'Climbing',items:[]}});
          scheduleFlush(50)}""")
        pg.wait_for_timeout(800)
        c.ok('offline work waits in the queue', pg.evaluate("lsGet(QKEY,[]).length") >= 1)
        c.ok('and is marked as waiting', pg.evaluate("plansCache().some(p=>p.pending)"))
        pg.context.set_offline(False)
        pg.evaluate("flushQueue()"); pg.wait_for_timeout(1500)
        c.ok('it goes through when you are back', pg.evaluate("lsGet(QKEY,[]).length") == 0
             and any(x['id'] == 'off1' for x in store['plans']), [x['id'] for x in store['plans']])

        # --- when the Sheet stops answering ---
        pg.context.route('https://script.google.com/**', lambda r: r.abort())
        pg.evaluate("pullPlans()"); pg.wait_for_timeout(1500)
        c.ok('it says the Sheet is not answering', 'Sync problem' in pg.inner_text('#syncline'),
             pg.inner_text('#syncline')[:60])
        c.ok('and offers to try again', pg.locator('[data-act=syncretry]').count() == 1)
        c.ok('the page stays the width of the screen',
             pg.evaluate("document.documentElement.scrollWidth<=innerWidth+1"))
        pg.context.unroute('https://script.google.com/**')
        pg.context.route('https://script.google.com/**', make_handler(store))
        pg.click('[data-act=syncretry]'); pg.wait_for_timeout(1800)
        c.ok('and recovers when it answers again', 'Sync problem' not in pg.inner_text('#syncline'),
             pg.inner_text('#syncline')[:60])

        # --- state backup ---
        pg.evaluate("""()=>{S.levels.toolhang=3;save();
          const q=lsGet(QKEY,[]).filter(o=>o.op!=='state');
          q.push({op:'state',state:JSON.parse(JSON.stringify(S)),qid:uid()});lsSet(QKEY,q);flushQueue()}""")
        pg.wait_for_timeout(1500)
        c.ok('settings are backed up', store['state'] and store['state'].get('levels', {}).get('toolhang') == 3)
        b.close()

        # --- a second browser picks everything up ---
        b2 = p.chromium.launch()
        ctx = b2.new_context(viewport={'width':375,'height':812}, is_mobile=True, has_touch=True, timezone_id='Europe/Oslo')
        ctx.route('https://script.google.com/**', make_handler(store))
        ctx.add_init_script(SYNC)
        pg2 = ctx.new_page(); errs2 = []
        pg2.on('pageerror', lambda e: errs2.append(str(e)))
        pg2.goto(URL); pg2.wait_for_timeout(800)
        pg2.evaluate("connectFlow()"); pg2.wait_for_timeout(1800)
        c.ok('connecting a new browser restores your slots', pg2.evaluate("S.levels.toolhang") == 3,
             pg2.evaluate("JSON.stringify(S.levels)"))
        pg2.click('#bnav [data-view=history]'); pg2.wait_for_timeout(1200)
        c.ok('and sees the plans', pg2.evaluate("plansCache().length") >= 1)
        c.ok('no errors anywhere', not errs and not errs2, errs + errs2)
        b2.close()
    return c.report()

if __name__ == '__main__':
    import sys; sys.exit(0 if run() else 1)
