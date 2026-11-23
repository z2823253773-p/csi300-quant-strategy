import re
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

def parse(expr):
    tokens=re.findall(r'\d+(?:\.\d*)?|\.\d+|[a-z_][a-z_0-9.]*|\|\||==|[(),?:^+*/<>-]',expr.lower())
    cursor=0
    def take():
        nonlocal cursor
        value=tokens[cursor];cursor+=1;return value
    def term(level=0):
        first=take()
        if first=='(':
            tree=term();assert take()==')'
        elif first=='-':tree=('neg',term(7))
        elif re.match(r'[\d.]',first):tree=float(first)
        elif tokens[cursor:cursor+1]==['(']:
            take();args=[term()]
            while tokens[cursor:cursor+1]==[',']:take();args.append(term())
            assert take()==')';tree=(first,*args)
        else:tree=first
        priority={'?':1,'||':2,'==':3,'<':3,'>':3,'+':4,'-':4,'*':5,'/':5,'^':6}
        while cursor<len(tokens) and priority.get(tokens[cursor],0)>level:
            op=take()
            if op=='?':
                yes=term();assert take()==':';tree=('where',tree,yes,term())
            else:tree=(op,tree,term(priority[op]))
        return tree
    result=term();assert cursor==len(tokens),(expr,tokens[cursor:]);return result

def window_op(frame,window,operation):
    length=int(window);values=frame.to_numpy();out=np.full(values.shape,np.nan)
    weights=np.arange(1,length+1,dtype=float);weights/=weights.sum()
    for start in range(0,values.shape[1],24):
        block=sliding_window_view(values[:,start:start+24],length,axis=0)
        if operation=='decay_linear':result=np.einsum('ijk,k->ij',block,weights)
        elif operation=='product':result=block.prod(axis=-1)
        else:
            result=(np.argmax(block,axis=-1) if operation=='ts_argmax' else np.argmin(block,axis=-1))+1.
            result[~np.isfinite(block).all(axis=-1)]=np.nan
        out[length-1:,start:start+24]=result
    return pd.DataFrame(out,index=frame.index,columns=frame.columns)

def evaluate(tree,env,mask,neutral):
    if not isinstance(tree,tuple):
        if isinstance(tree,float):return tree
        if tree.startswith('indclass.'):return tree
        if tree.startswith('adv') and tree not in env:env[tree]=env['amount'].rolling(int(tree[3:])).mean()
        return env[tree]
    op=tree[0];args=[evaluate(item,env,mask,neutral) for item in tree[1:]];left=args[0];right=args[1] if len(args)>1 else None
    if op in ['<','>','==','||']:
        fn={'<':np.less,'>':np.greater,'==':np.equal,'||':np.logical_or}[op]
        return fn(left,right).astype(float).where(np.isfinite(left)&np.isfinite(right))
    if op=='where':
        result=pd.DataFrame(np.where(left!=0,right,args[2]),index=mask.index,columns=mask.columns);return result.where(left.notna())
    if op in ['+','-','*','/','^','signedpower']:
        value={'+':np.add,'-':np.subtract,'*':np.multiply,'/':np.divide,'^':np.power,'signedpower':np.power}[op](left,right)
        return value.replace([np.inf,-np.inf],np.nan) if isinstance(value,pd.DataFrame) else value
    if op=='neg':return -left
    if op in ['log','abs','sign']:
        return {'log':np.log,'abs':np.abs,'sign':np.sign}[op](left).replace([np.inf,-np.inf],np.nan)
    if op=='rank':return left.where(mask).rank(axis=1,pct=True)
    if op=='scale':
        eligible=left.where(mask);return eligible.div(eligible.abs().sum(axis=1).replace(0,np.nan),axis=0)*(1 if right is None else right)
    if op=='indneutralize':return neutral(left.where(mask))
    if op in ['min','max'] and isinstance(right,pd.DataFrame):return (np.minimum if op=='min' else np.maximum)(left,right)
    if op in ['correlation','covariance']:
        rolling=left.rolling(int(args[2]))
        if op=='covariance':return rolling.cov(right)
        result=rolling.corr(right).replace([np.inf,-np.inf],np.nan)
        return result.where((rolling.max()>rolling.min())&(right.rolling(int(args[2])).max()>right.rolling(int(args[2])).min())).clip(-1,1)
    if op in ['product','ts_argmin','ts_argmax','decay_linear']:return window_op(left,right,op)
    if op=='delta':return left.diff(int(right))
    if op=='delay':return left.shift(int(right))
    rolling=left.rolling(int(right))
    if op=='ts_rank':return rolling.rank(pct=True)
    return getattr(rolling,{'min':'min','max':'max','ts_min':'min','ts_max':'max','sum':'sum','stddev':'std'}[op])()
