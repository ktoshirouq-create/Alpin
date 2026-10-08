"""Opens every screen and sheet at phone width and looks for layout faults:
things wider than the screen, uneven control rows, footers off-screen, very long sheets."""
from playwright.sync_api import sync_playwright
from harness import page, new_store

# --- extra guards added after the shell change: the bar must stay visible and the
# layout must never be wider than the screen on any view ---
def shell_checks(pg, issues):
    for v in ['today', 'train', 'history']:
        pg.click(f'#bnav [data-view={v}]'); pg.wait_for_timeout(400)
        d = pg.evaluate("""()=>{const b=document.getElementById('bnav'),r=b.getBoundingClientRect();
          return {top:Math.round(r.top),bottom:Math.round(r.bottom),vh:innerHeight,
                  inner:innerWidth,docW:document.documentElement.scrollWidth}}""")
        if d['bottom'] > d['vh'] + 1 or d['top'] < 0:
            issues.append(f"{v}: the bottom bar is off the screen ({d})")
        if d['docW'] > d['inner'] + 1:
            issues.append(f"{v}: the page is wider than the screen ({d['docW']} > {d['inner']})")


def run():
    issues = []
    store = new_store()
    with sync_playwright() as p:
        b, pg, errs = page(p, store, width=360, height=740)
        pg.on('pageerror', lambda e: issues.append('JS ERROR ' + str(e)))

        def check(where):
            for x in pg.evaluate("""()=>{const out=[],W=innerWidth;
              document.querySelectorAll('dialog[open] *,body>main *').forEach(el=>{
                const r=el.getBoundingClientRect(); if(!r.width) return;
                if(r.right>W+1||r.left<-1) out.push((el.className||el.tagName)+' '+Math.round(r.left)+'→'+Math.round(r.right));});
              return out.slice(0,4)}"""):
                issues.append(f'{where}: wider than the screen · {x}')
            d = pg.evaluate("""()=>{const d=document.querySelector('dialog[open]');if(!d)return null;
              const f=d.querySelector('form')||d;return {scroll:Math.round(f.scrollHeight-f.clientHeight),vh:innerHeight}}""")
            if d and d['scroll'] > d['vh'] * 1.2:
                issues.append(f"{where}: sheet scrolls {round(d['scroll']/d['vh'],1)} screens")
            for x in pg.evaluate("""()=>{const out=[];
              document.querySelectorAll('dialog[open] .durchips,dialog[open] .typechips,dialog[open] .rail').forEach(row=>{
                const k=[...row.children].filter(x=>x.tagName==='BUTTON'&&x.getBoundingClientRect().width>0);
                if(k.length<2)return; const w=k.map(x=>x.getBoundingClientRect().width);
                if(Math.max(...w)>Math.min(...w)*3.2) out.push(row.className+' '+w.map(Math.round).join('/'));});
              return out}"""):
                issues.append(f'{where}: uneven control row · {x}')
            # a footer may sit below the fold in a sheet you scroll; only flag it when the sheet does not scroll
            foot = pg.evaluate("""()=>{const dlg=document.querySelector('dialog[open]');if(!dlg)return false;
              const f=dlg.querySelector('form')||dlg,d=dlg.querySelector('.dbtns');if(!d)return false;
              const scrolls=f.scrollHeight-f.clientHeight>4;
              return !scrolls && d.getBoundingClientRect().bottom>innerHeight+1}""")
            if foot: issues.append(f'{where}: footer buttons off the screen')

        for view in ['today','train','history']:
            pg.click(f'#bnav [data-view={view}]'); pg.wait_for_timeout(450); check(view)
        for h in ['#climb','#run','#warmup','#ice','#nepal','#toubkal','#oslo','#passes']:
            pg.goto(pg.url.split('#')[0] + h); pg.wait_for_timeout(450); check(h)

        pg.click('#bnav [data-view=history]'); pg.wait_for_timeout(500)
        pg.click('[data-act=plannew]'); pg.wait_for_timeout(350); check('plan sheet')
        pg.click('[data-pa=Hike]'); pg.wait_for_timeout(250); check('plan sheet · hike')
        if pg.is_visible('#paUpLab') is False: issues.append('plan sheet: a hike has no ascent field')
        for t in ['Climbing','Bouldering','Other']:
            pg.click(f'[data-pa={t}]'); pg.wait_for_timeout(180)
            if pg.is_visible('#paKmLab'): issues.append(f'plan sheet: distance field shows for {t}')
        pg.click('#planfrm button[value=cancel]'); pg.wait_for_timeout(250)

        pg.click('[data-act=tripnew]'); pg.wait_for_timeout(300); check('new trip')
        pg.fill('#tripnewfrm [name=name]','Audit'); pg.fill('#tripnewfrm [name=start]','2026-10-27')
        pg.fill('#tripnewfrm [name=end]','2026-10-28'); pg.click('#tripnewfrm button[value=save]')
        pg.wait_for_timeout(600); check('trip editor')
        w = pg.evaluate("[...document.querySelectorAll('#trRail .day')].map(d=>Math.round(d.getBoundingClientRect().width))")
        if w and max(w) > min(w) * 1.6: issues.append(f'trip editor: day pills uneven {w}')
        pg.click('#tripfrm button[value=cancel]'); pg.wait_for_timeout(250)

        pg.click('[data-act=weekbuild]'); pg.wait_for_timeout(500); check('build a week')
        pg.click('#weekfrm button[value=cancel]'); pg.wait_for_timeout(250)
        pg.click('[data-act=runweek]'); pg.wait_for_timeout(900); check('running week')
        pg.click('#runweekfrm button[value=cancel]'); pg.wait_for_timeout(250)
        shell_checks(pg, issues)
        issues += ['JS ERROR ' + e for e in errs]
        b.close()
    print('\n'.join(issues) if issues else 'no layout issues')
    print('---', len(issues), 'issues')
    return not issues

if __name__ == '__main__':
    import sys; sys.exit(0 if run() else 1)
