"""Train tab: structure, rows, slots, your own changes, the timer."""
from playwright.sync_api import sync_playwright
from harness import page, Checks, gotab, openrow

def run():
    c = Checks('core')
    with sync_playwright() as p:
        b, pg, errs = page(p, connected=False)

        # --- tabs and structure ---
        tabs = pg.evaluate("TRAIN_IDS.map(id=>PROGS.find(x=>x.id===id).chip)")
        c.ok('five train tabs', tabs == ['Nepal','Ice','Climbing','Run','Warm up'], tabs)
        dupes = pg.evaluate("""TRAIN_IDS.map(id=>{const p=PROGS.find(x=>x.id===id),seen={},d=[];
          p.sections.forEach((s,i)=>sectionItems(p,i).forEach(e=>{if(seen[e.id])d.push(id+':'+e.id);seen[e.id]=1}));return d}).flat()""")
        c.ok('no exercise appears twice in a tab', dupes == [], dupes)
        warm = pg.evaluate("PROGS.find(p=>p.id==='warmup').sections.map(s=>s.title)")
        c.ok('warm up holds the four routines', warm == ['Pre-run','Pre-workout','Pre-climb','Stretch'], warm)
        c.ok('warm-up moves live only there', pg.evaluate(
            "['pulse','handwarm','basetraverse','hipflex','catcow'].every(id=>['nepal','ice','climb','run']"
            ".every(t=>{const p=PROGS.find(x=>x.id===t);return p.sections.every((s,i)=>sectionItems(p,i).every(e=>e.id!==id))}))"))

        # --- every tab renders cleanly ---
        for pid in ['nepal','ice','climb','run','warmup']:
            gotab(pg, pid)
            txt = pg.inner_text('main')
            c.ok(f'{pid}: renders', pg.locator('.exrow').count() + pg.locator('.runcard,.rundash,.wkcard').count() > 0
                 and 'undefined' not in txt and 'NaN' not in txt)
            c.ok(f'{pid}: drawings clean', pg.evaluate(
                """()=>{const p=prog();let bad=0;p.sections.forEach((s,i)=>sectionItems(p,i).forEach(e=>
                   (e.frames||[]).forEach(f=>{if(/NaN|undefined/.test(frameSVG(f)))bad++})));return bad}""") == 0)
            c.ok(f'{pid}: no sideways scroll',
                 not pg.evaluate("document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))

        # --- compact rows and section pills ---
        gotab(pg, 'climb')
        c.ok('section pills plus Select', pg.locator('.secbar .spill').count() >= 3 and pg.locator('.spill.sel').count() == 1)
        c.ok('rows are compact by default', pg.locator('.exrow').count() >= 4 and pg.locator('.ex.open').count() == 0)
        pg.click('.exrow[data-id=pullup]'); pg.wait_for_timeout(250)
        c.ok('tap opens one card', pg.locator('.ex.open').count() == 1 and pg.locator('.ex.open .frames').count() == 1)
        pg.click('.exrow[data-id=scap]'); pg.wait_for_timeout(250)
        c.ok('only one card at a time', pg.locator('.ex.open').count() == 1
             and pg.get_attribute('.ex.open', 'data-id') == 'scap')

        # --- done, undo, counts ---
        pg.click('.ex.open [data-act=logdone]'); pg.wait_for_timeout(300)
        c.ok('the card says it is logged', pg.locator('.ex.open.donecard .loggedline').count() == 1)
        pg.click('[data-act=collapse]'); pg.wait_for_timeout(200)
        c.ok('the row is ticked', pg.locator('.exrow.done[data-id=scap]').count() == 1)
        c.ok('the section counts it', '1 of' in pg.inner_text('.donecount >> nth=1'))
        pg.click('.exrow.done[data-id=scap] [data-act=unlog]'); pg.wait_for_timeout(250)
        c.ok('undo from the row', pg.locator('.exrow.done').count() == 0)

        # --- slots ---
        gotab(pg, 'ice'); openrow(pg, 'toolhang')
        c.ok('five slots, one chosen', pg.locator('.ex.open .dots input').count() == 5
             and pg.locator('.ex.open .dots input:checked').count() == 1)
        pg.locator('.ex.open .dots input[value="2"]').tap(); pg.wait_for_timeout(200)
        c.ok('tapping a slot changes the dose', pg.evaluate("S.levels.toolhang") == 2
             and '3 ×' in pg.inner_text('.exrow[data-id=toolhang] .rdose, .ex.open .dose'))
        pg.reload(); pg.wait_for_timeout(400)
        c.ok('the slot survives a reload', pg.evaluate("S.levels.toolhang") == 2)
        gotab(pg, 'nepal'); openrow(pg, 'calf')
        pg.locator('.ex.open .dots input[value="3"]').tap(); pg.wait_for_timeout(200)
        gotab(pg, 'ice')
        c.ok('a shared exercise shares its slot', pg.evaluate("S.levels.calf") == 3)

        # --- hide and bring back ---
        gotab(pg, 'nepal'); openrow(pg, 'plank')
        pg.click('.ex.open [data-act=hide]'); pg.wait_for_timeout(250)
        c.ok('hidden exercises leave the list', pg.locator('.exrow[data-id=plank]').count() == 0
             and pg.evaluate("S.hidden.length") == 1)
        pg.evaluate("()=>{const b=document.querySelector('[data-act=unhide]');if(b)b.click()}"); pg.wait_for_timeout(250)
        c.ok('and come back', pg.evaluate("S.hidden.length") == 0)

        # --- the timer ---
        gotab(pg, 'ice'); openrow(pg, 'toolhang')
        pg.locator('.ex.open [data-act=one]').tap(); pg.wait_for_timeout(200)
        c.ok('start screen keeps the numbers behind Adjust', pg.locator('#faBody .faadj summary').count() == 1)
        pg.click('#faGo'); pg.clock.run_for(5400)
        c.ok('counts down, then work', pg.inner_text('#faLbl').startswith('Rep 1')
             and pg.evaluate("fa.classList.contains('ph-work')"), pg.inner_text('#faLbl'))
        pg.clock.run_for(11000)
        c.ok('then rest', pg.inner_text('#faLbl') == 'Rest' and pg.evaluate("fa.classList.contains('ph-rest')"))
        c.ok('live controls appear in the rest', pg.is_visible('#faLive') and pg.locator('[data-live=rest30]').count() == 1)
        left = pg.evaluate('F.left'); pg.click('[data-live=rest30]')
        c.ok('+30 s rest', pg.evaluate('F.left') - left == 30)
        n = pg.evaluate('F.ph.length'); pg.click('[data-live=again]')
        c.ok('repeat a rep', pg.evaluate('F.ph.length') > n)
        n = pg.evaluate('F.ph.length'); pg.click('[data-live=addset]')
        c.ok('add a set', pg.evaluate('F.ph.length') > n)
        pg.click('[data-live=slot][data-i="3"]'); pg.wait_for_timeout(200)
        c.ok('change slot mid-session', pg.evaluate('S.levels.toolhang') == 3)
        c.ok('Back steps through the session', pg.inner_text('#faPrev') == 'Back a step')
        pg.evaluate("document.getElementById('faPrev').click()"); pg.wait_for_timeout(150)
        c.ok('and it moves', pg.evaluate('F.p') >= 0)
        pg.click('#faX'); pg.wait_for_timeout(200)
        if pg.locator('[data-act=discard]').count(): pg.click('[data-act=discard]')

        c.ok('no errors', not errs, errs)
        b.close()
    return c.report()



def run_stair44():
    """The guided stair 4 × 4: warm-up, four reps with easy between, cool-down, coaching lines."""
    from playwright.sync_api import sync_playwright as _sp
    from harness import page as _page, Checks as _Checks, gotab as _gotab, openrow as _openrow
    c = _Checks('stair 4 × 4')
    with _sp() as p:
        b, pg, errs = _page(p, connected=False)
        _gotab(pg, 'nepal')
        c.ok('it sits in Nepal endurance',
             'stair44' in pg.evaluate("sectionItems(prog(),1).map(e=>e.id).join()"))
        _openrow(pg, 'stair44')
        pg.locator('.ex.open .dots input[value="2"]').tap(); pg.wait_for_timeout(250)
        ph = pg.evaluate("phasesOf(resolve('stair44','nepal')).map(p=>p.l)")
        c.ok('warm-up first, cool-down last', ph[0].startswith('Warm up') and ph[-1].startswith('Cool down'), ph)
        c.ok('four hard reps', len([x for x in ph if x.startswith('Rep')]) == 4, ph)
        c.ok('three easy stretches between them', len([x for x in ph if x.startswith('Easy')]) == 3, ph)
        c.ok('about three quarters of an hour',
             40 <= pg.evaluate("Math.round(totalOf(resolve('stair44','nepal'))/60)") <= 46)
        c.ok('it knows your stairs', 'trips up and down' in pg.inner_text('.ex.open .lapline'))
        pg.locator('.ex.open [data-act=one]').tap(); pg.wait_for_timeout(250); pg.click('#faGo')
        pg.clock.run_for(5400)
        c.ok('it talks you through the warm-up', 'Warm up' in pg.inner_text('#faLbl')
             and 'talk' in pg.inner_text('#faNote'), pg.inner_text('#faNote')[:40])
        pg.clock.run_for(601000)
        c.ok('and the first rep', pg.inner_text('#faLbl').startswith('Rep 1')
             and 'steadier' in pg.inner_text('#faNote'))
        pg.clock.run_for(241000)
        c.ok('and the recovery', 'Easy' in pg.inner_text('#faLbl') and 'Keep moving' in pg.inner_text('#faNote'))
        pg.click('#faX'); pg.wait_for_timeout(200)
        if pg.locator('[data-act=discard]').count(): pg.click('[data-act=discard]')
        c.ok('no errors', not errs, errs)
        b.close()
    return c.report()

if __name__ == '__main__':
    import sys; ok = run(); ok = run_stair44() and ok; sys.exit(0 if ok else 1)
