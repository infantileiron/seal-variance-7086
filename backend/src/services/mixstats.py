EPS=1e-9
METHOD=('同批均值差配比敏感性：按批次聚合现行拉力样本，每对工艺在每个批次得到批内均值差 d_b；订单配比 w 需满足各批上下限且合计为 1，'
        '整体差值 D(w)=Σw_b·d_b 是关于 w 的线性函数，在可行域顶点达到最小/最大（按 d_b 排序贪心分配份额求得）；'
        '可能分到份额（max_share>0）的批次若缺少任一工艺的样本组，该工艺对不出结论；占比上下限无可行解时整体不出结论。')
def _cells(samples):
    cells={}
    for s in samples:cells.setdefault((s['process_id'],s['lot']),[]).append(s['force'])
    return cells
def _mix(lots,diffs,reverse):
    w={b['lot']:b['lower'] for b in lots}
    rest=1-sum(b['lower'] for b in lots)
    key=lambda b:(-diffs.get(b['lot'],0.),b['lot']) if reverse else (diffs.get(b['lot'],0.),b['lot'])
    for b in sorted(lots,key=key):
        if rest<=EPS:break
        add=min(max(0.,b['max_share']-b['lower']),rest)
        w[b['lot']]+=add;rest-=add
    return w
def analyze(processes,samples,bounds):
    lots=[{'lot':b['lot'],'lower':b['lower'],'upper':b['upper']} for b in bounds]
    base={'feasible':True,'lots':lots,'pairs':[],'ignored_lots':[],'conclusion':None,'complete':False,'no_conclusion_reason':None,'method':METHOD}
    if not lots:
        base.update(feasible=False,no_conclusion_reason='尚未录入任何批次占比上下限，无可行配比集合。');return base
    for b in lots:
        if b['lower']<-EPS or b['upper']>1+EPS or b['lower']>b['upper']+EPS:
            base.update(feasible=False,no_conclusion_reason=f"批次 {b['lot']} 的上下限 {b['lower']}~{b['upper']} 自身矛盾，占比无解。");return base
    slo=sum(b['lower'] for b in lots);shi=sum(b['upper'] for b in lots)
    base['share_sum']={'lower':slo,'upper':shi}
    if slo>1+EPS or shi<1-EPS:
        base.update(feasible=False,no_conclusion_reason=f'占比无解：下限合计 {slo:.3f}、上限合计 {shi:.3f}，不存在合计为 1 的配比。');return base
    for b in lots:b['max_share']=min(b['upper'],1-(slo-b['lower']))
    active=[b for b in lots if b['max_share']>EPS]
    cells=_cells(samples)
    mean={k:sum(v)/len(v) for k,v in cells.items()}
    bounded={b['lot'] for b in lots}
    base['ignored_lots']=sorted({s['lot'] for s in samples}-bounded)
    pairs=[]
    for i in range(len(processes)):
        for j in range(i+1,len(processes)):
            A,B=processes[i],processes[j]
            pair={'a':{'id':A['id'],'code':A['code'],'name':A['name']},'b':{'id':B['id'],'code':B['code'],'name':B['name']}}
            missing=[{'lot':b['lot'],'process':p['code']} for b in active for p in (A,B) if (p['id'],b['lot']) not in cells]
            if missing:pair.update(status='missing_groups',missing=missing)
            else:
                diffs={b['lot']:mean[(A['id'],b['lot'])]-mean[(B['id'],b['lot'])] for b in active}
                pair['diffs']=[{'lot':b['lot'],'n_a':len(cells[(A['id'],b['lot'])]),'n_b':len(cells[(B['id'],b['lot'])]),'mean_a':mean[(A['id'],b['lot'])],'mean_b':mean[(B['id'],b['lot'])],'d':diffs[b['lot']]} for b in active]
                wmin=_mix(lots,diffs,False);wmax=_mix(lots,diffs,True)
                dmin=sum(wmin[b['lot']]*diffs[b['lot']] for b in active);dmax=sum(wmax[b['lot']]*diffs[b['lot']] for b in active)
                verdict='a_leads' if dmin>EPS else 'b_leads' if dmax<-EPS else 'tie' if abs(dmin)<=EPS and abs(dmax)<=EPS else 'flip'
                pair.update(status='ok',range={'min':dmin,'max':dmax},min_mix=wmin,max_mix=wmax,verdict=verdict)
            pairs.append(pair)
    base['pairs']=pairs
    decided=[p for p in pairs if p['status']=='ok']
    base['complete']=len(decided)==len(pairs)
    if decided:
        parts=[]
        for p in decided:
            rng=f"[{p['range']['min']:.3f}, {p['range']['max']:.3f}]N"
            if p['verdict']=='a_leads':parts.append(f"{p['a']['code']} 相对 {p['b']['code']} 在全部可行配比下保持领先（差值 {rng}）")
            elif p['verdict']=='b_leads':parts.append(f"{p['a']['code']} 相对 {p['b']['code']} 在全部可行配比下处于落后（差值 {rng}）")
            elif p['verdict']=='tie':parts.append(f"{p['a']['code']} 与 {p['b']['code']} 在可行配比下基本持平（差值 {rng}）")
            else:parts.append(f"{p['a']['code']} 与 {p['b']['code']} 的高低随配比翻转（差值 {rng} 跨越 0，订单换配比后排名可能互换）")
        if not base['complete']:parts.append(f"另有 {len(pairs)-len(decided)} 对因可能分到份额的批次缺组未出结论")
        base['conclusion']='；'.join(parts)+'。'
    else:base['no_conclusion_reason']='每对工艺都遇到可能分到份额的批次缺组，本次不出结论。'
    return base
