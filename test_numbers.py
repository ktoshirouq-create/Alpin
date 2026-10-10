"""Numbers: weekly kilometres, the pace marker, the marathon plan and its nudges."""
from playwright.sync_api import sync_playwright
from harness import page, Checks, new_store, gotab, seed_plans, seed_log

def run():
    c = Checks('numbers')
    store = new_store()
    with sync_playwright() as p:
        b, pg, errs = page(p, store, when=(2026, 10, 4, 8, 0))

        # a week with one logged run and one ticked-but-unlogged run
        seed_plans(pg, [
            {'id':'p1','date':'2026-09-28','start':'12:00','minutes':35,'title':'Easy run · 4.5 km',
             'tab':'Run','items':['Easy run: 4.5 km'],'status':'done'},
            {'id':'p2','date':'2026-10-02','start':'12:00','minutes':60,'title':'Long run · 10 km',
             'tab':'Run','items':['Long run: 10 km'],'status':'done'}])
        pg.evaluate("()=>{S.runMeta.p1={type:'easy',km:4.5};S.runMeta.p2={type:'long',km:10};save()}")
        seed_log(pg, [{'id':'l2','date':'2026-10-02','time':'14:56','tab':'Run','exercise_id':'runlong',
                       'exercise':'Long run','completed':'10.17 km','result':'done','plan_id':'p2'}])
        pg.wait_for_timeout(300)
        km = round(pg.evaluate("runKmIn(mondayOf(new Date()))"), 2)
        c.ok('a run ticked done without a log still counts', km == 14.67, km)
        c.ok('Today shows the week total', '14.7' in pg.inner_text('main'))
        pg.evaluate("""()=>{const l=localLog();l.push({id:'l1',date:'2026-09-28',time:'13:00',tab:'Run',
          exercise_id:'runeasy',exercise:'Easy run',completed:'4.6 km',result:'done',plan_id:'p1'});
          setLocalLog(l);refresh()}""")
        pg.wait_for_timeout(250)
        c.ok('a real log replaces the plan, never both',
             round(pg.evaluate("runKmIn(mondayOf(new Date()))"), 2) == 14.77)
        seed_plans(pg, pg.evaluate("plansCache()") + [
            {'id':'p3','date':'2026-10-03','start':'10:00','minutes':40,'title':'Easy run · 6 km',
             'tab':'Run','items':[],'status':'planned'}])
        pg.wait_for_timeout(250)
        c.ok('an unticked plan counts for nothing',
             round(pg.evaluate("runKmIn(mondayOf(new Date()))"), 2) == 14.77)

        # the run tab
        gotab(pg, 'run'); pg.wait_for_timeout(400)
        c.ok('pace marker on the bar', pg.locator('.kmbar u').count() == 1)
        c.ok('ahead or behind is spelled out',
             any(w in pg.inner_text('.kmtxt') for w in ['behind','ahead','on track']), pg.inner_text('.kmtxt'))
        c.ok('the week runs show as chips', pg.locator('.rchip').count() >= 1)
        c.ok('eight weeks of history', pg.locator('.wkchart span').count() == 8)
        c.ok('no planner buttons here', pg.locator('[data-act=runweek]').count() == 0)

        # the plan itself
        W = pg.evaluate("weekInfo(new Date())")
        c.ok('week info is sane', W['idx'] >= 1 and W['target'] > 0 and W['long'] > 0, W)
        c.ok('phases run base to taper',
             pg.evaluate("[...new Set([0,10,30,45,51].map(i=>weekInfo(addDays(mondayOf(new Date()),i*7)).phase.name))].length") >= 3)
        c.ok('trail is a run kind', pg.evaluate("RUNLBL.trail") == 'Trail run'
             and pg.evaluate("runPace('trail')>runPace('easy')"))
        c.ok('zones per type', pg.evaluate("zoneText(RUNZONE.easy).includes('Zone 2')"))

        # suggestions skip days you are away
        pg.evaluate("""()=>{S.trips={t9:{id:'t9',name:'Away',start:dayOf(addDays(mondayOf(new Date()),7)),
          end:dayOf(addDays(mondayOf(new Date()),10)),kind:'Hike'}};save();refresh()}""")
        sug = pg.evaluate("suggestWeek(addDays(mondayOf(new Date()),7)).runs.map(r=>r.date)")
        away = pg.evaluate("[...tripDays()]")
        c.ok('no runs planned into a trip', all(d not in away for d in sug), (sug, away[:4]))

        c.ok('no errors', not errs, errs)
        b.close()
    return c.report()



def run_pairing():
    """One session, one line: plans pair with their log; gym exercises pool."""
    from playwright.sync_api import sync_playwright as _sp
    from harness import page as _page, Checks as _Checks, new_store as _store, seed_log as _log
    c = _Checks('pairing and pooling')
    store = _store()
    store['plans'] = [
        {'id':'p5','date':'2026-10-05','start':'11:00','minutes':40,'title':'Easy run · 5 km','tab':'Run',
         'items':['Zone 2 · 133–146 bpm'],'status':'done'},
        {'id':'p6','date':'2026-10-07','start':'09:00','minutes':60,'title':'Climbing · indoor','tab':'Climbing',
         'items':[],'status':'planned'}]
    with _sp() as p:
        b, pg, errs = _page(p, store, when=(2026, 10, 10, 8, 0))
        _log(pg, [
            {'id':'r1','date':'2026-10-05','time':'15:12','tab':'Run','exercise_id':'runeasy','exercise':'Easy run',
             'completed':'6.3 km','dose':'6.3 km · 44 min','result':'done','seconds':'2640'},
            {'id':'g1','date':'2026-10-10','time':'12:23','tab':'Ice','exercise_id':'scap','exercise':'Scapular pull-ups','dose':'2 × 8','result':'done','seconds':'300'},
            {'id':'g2','date':'2026-10-10','time':'12:30','tab':'Ice','exercise_id':'knee','exercise':'Hanging knee raises','dose':'2 × 6','result':'done','seconds':'240'},
            {'id':'g3','date':'2026-10-10','time':'12:43','tab':'Ice','exercise_id':'toolhang','exercise':'Ice tool hangs','dose':'2 × 6 × 10 s','result':'done','seconds':'480'},
            {'id':'g4','date':'2026-10-10','time':'19:40','tab':'Ice','exercise_id':'calf','exercise':'Calf raise','dose':'2 × 15','result':'done','seconds':'200'}])
        pg.click('#bnav [data-view=history]'); pg.wait_for_timeout(1200)
        pg.click('.cd[data-d="2026-10-05"]'); pg.wait_for_timeout(400)
        c.ok('a run you logged pairs with the plan you ticked',
             pg.locator('.prow').count() == 1 and pg.locator('.hrow').count() == 0,
             (pg.locator('.prow').count(), pg.locator('.hrow').count()))
        c.ok('and the card carries the real result',
             '6.3 km' in pg.inner_text('.prow') and 'done' in pg.inner_text('.prow'))
        pg.click('.cd[data-d="2026-10-10"]'); pg.wait_for_timeout(400)
        c.ok('exercises close together become one session', pg.locator('.hrow.pool').count() == 1)
        c.ok('the pool says what and when',
             '3 exercises' in pg.inner_text('.hrow.pool summary')
             and '12:23' in pg.inner_text('.hrow.pool summary'), pg.inner_text('.hrow.pool summary'))
        c.ok('a session hours later stays separate',
             pg.evaluate("""()=>{const rows=[...document.querySelectorAll('.hday > .hrow')];
               return rows.filter(r=>!r.classList.contains('pool')).length}""") == 1)
        pg.click('.hrow.pool summary'); pg.wait_for_timeout(250)
        c.ok('and opens into its exercises', pg.locator('.poolin .hrow').count() == 3)
        pg.click('.cd[data-d="2026-10-07"]'); pg.wait_for_timeout(400)
        c.ok('an unfinished plan is untouched',
             pg.locator('.prow').count() == 1 and 'done' not in pg.inner_text('.prow'))
        c.ok('no errors', not errs, errs)
        b.close()
    return c.report()

if __name__ == '__main__':
    import sys; ok = run(); ok = run_pairing() and ok; sys.exit(0 if ok else 1)
