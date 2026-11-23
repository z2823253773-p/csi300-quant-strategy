from pathlib import Path
import pandas as pd,numpy as np,json,argparse
parser=argparse.ArgumentParser();parser.add_argument('--old',type=Path,required=True);parser.add_argument('--new',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
old=args.old;new=args.new
out=args.out;out.mkdir(parents=True,exist_ok=True)
rows=[]
for p in old.glob('matrix_*.parquet'):
 a=pd.read_parquet(p);b=pd.read_parquet(new/p.name);a.index=a.index.as_unit('ns');b.index=b.index.as_unit('ns');pd.testing.assert_index_equal(a.index,b.index);pd.testing.assert_index_equal(a.columns,b.columns)
 eq=(a==b)|(a.isna()&b.isna());rows.append({'file':p.name,'cells':a.size,'changed':int((~eq).sum().sum())})
pd.DataFrame(rows).to_csv(out/'data_matrix_diff.csv',index=False,encoding='utf-8-sig')
a=pd.read_parquet(old/'clean_daily_panel.parquet').set_index(['trade_date','stock_code']).sort_index()
b=pd.read_parquet(new/'clean_daily_panel.parquet').set_index(['trade_date','stock_code']).sort_index()
assert list(a.index)==list(b.index)
rows=[]
for k in a.columns.intersection(b.columns):
 eq=(a[k]==b[k])|(a[k].isna()&b[k].isna());n=int((~eq).sum())
 if n:rows.append({'field':k,'changed':n})
pd.DataFrame(rows).to_csv(out/'data_panel_diff.csv',index=False,encoding='utf-8-sig')
known=b.sw_l1_name.notna()&b.sw_l1_name.ne('未分类');tr=b.tradable_mask
cov=pd.DataFrame({'tradable':tr,'known':tr&known,'unknown':tr&~known}).groupby(level=0).sum();cov['unknown_fraction']=cov.unknown/cov.tradable
cov.to_csv(out/'industry_coverage.csv',encoding='utf-8-sig')
info={'panel_rows':len(b),'new_fields':b.columns.difference(a.columns).tolist(),'unknown_all_fraction':float((~known).mean()),'unknown_tradable_fraction':float((tr&~known).sum()/tr.sum()),'old_industry_schemes':a.industry_scheme.value_counts(dropna=False).to_dict(),'new_industry_schemes':b.industry_scheme.fillna('missing').value_counts().to_dict(),'age_summary':b[['peTTM_age_days','pbMRQ_age_days']].describe().to_dict()}
(out/'data_audit.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(info,ensure_ascii=False,indent=2));print(pd.DataFrame(rows).to_string(index=False))
