import unittest
import numpy as np
import pandas as pd
from research import factors, clean, label, rank
from extensions import proportion_factors,drift,turnover

class ResearchTests(unittest.TestCase):
    def test_proportional_invariance(self):
        c=pd.DataFrame([[10.,100.],[12.,80.],[11.,90.]])
        m=dict(close_hfq=c,open_hfq=c*.99,high_hfq=c*1.02,low_hfq=c*.98,volume=c*10)
        n={k:(v*pd.Series([.1,100])) if k!='volume' else v for k,v in m.items()}
        for k,v in proportion_factors(m).items():np.testing.assert_allclose(v,proportion_factors(n)[k],equal_nan=True)
        m['high_hfq']=m['low_hfq'];self.assertTrue(proportion_factors(m)['new101_range'].isna().all().all())
    def test_drift_and_turnover(self):
        gross,w=drift(np.array([.5,.5]),np.array([.2,0.]));self.assertAlmostEqual(gross,.1)
        np.testing.assert_allclose(w,[6/11,5/11]);b,s=turnover(w,np.array([.5,.5]))
        self.assertAlmostEqual(b,1/22);self.assertAlmostEqual(s,1/22)
        self.assertEqual(turnover(np.zeros(2),np.array([.5,.5])),(1.,0.))
    def test_hand_computed_formula(self):
        t=np.arange(15.)[:,None]; c=pd.DataFrame(20+t+np.arange(3)[None,:]);o=c-1;v=c*10
        r=c.pct_change(fill_method=None);mask=c.notna()
        f=factors(dict(open_hfq=o,close_hfq=c,high_hfq=c+1,low_hfq=c-2,volume=v,returns=r,mask=mask))
        np.testing.assert_allclose(f['alpha006'].iloc[-1],-1,atol=1e-8)
        np.testing.assert_allclose(f['alpha012'].iloc[-1],-1)
        np.testing.assert_allclose(f['alpha101'].iloc[-1],1/3.001)
        np.testing.assert_allclose(f['alpha033'].iloc[-1],[1/3,2/3,1])
        np.testing.assert_allclose(f['alpha014'].iloc[-1],-rank(r.diff(3)).iloc[-1],atol=1e-8)
    def test_neutral_orthogonality(self):
        rng=np.random.default_rng(42);x=pd.DataFrame(rng.normal(size=(4,100)))
        s=pd.DataFrame(rng.normal(size=(4,100)));ind=pd.DataFrame(np.tile(np.repeat(['A','B'],50),(4,1)))
        z=clean(x,x.notna(),s,ind,True)
        for t in range(4):
            self.assertAlmostEqual(float(z.iloc[t]@s.iloc[t]),0,places=9)
            self.assertAlmostEqual(z.iloc[t,:50].mean(),0,places=9)
            self.assertAlmostEqual(z.iloc[t].std(),1,places=9)
    def test_label_and_missing(self):
        p=pd.DataFrame({'a':np.arange(1.,15)})
        self.assertEqual(label(p,5).iloc[0,0],7/2-1)
        self.assertTrue(label(p,5).tail(6).isna().all().all())
        p.iloc[1,0]=np.nan
        self.assertTrue(np.isnan(label(p,5).iloc[0,0]))
    def test_rank_excludes_outside_universe(self):
        c=pd.DataFrame([[10.,20.,30.]]);o=pd.DataFrame([[9.,18.,29.]])
        m=dict(open_hfq=o,close_hfq=c,high_hfq=c,low_hfq=o,volume=c,returns=c,mask=pd.DataFrame([[True,True,False]]))
        a=factors(m)['alpha033'];self.assertTrue(np.isnan(a.iloc[0,2]));np.testing.assert_allclose(a.iloc[0,:2],[.75,.75])

if __name__=='__main__':unittest.main()
