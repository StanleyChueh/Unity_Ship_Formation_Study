import numpy as np,sys
res=np.load(sys.argv[1],allow_pickle=True)
def fit_gauss(X):  # MLE mean/cov
    mu=X.mean(0);S=np.cov(X.T,bias=True)+1e-4*np.eye(X.shape[1]);return mu,S
def loglik(X,mu,S):
    d=X-mu;Si=np.linalg.inv(S);_,ld=np.linalg.slogdet(S)
    return -0.5*np.einsum('ij,jk,ik->i',d,Si,d)-0.5*ld
def auc(y,s):
    o=np.argsort(s);r=np.empty(len(s));r[o]=np.arange(1,len(s)+1);n1=y.sum();n0=len(y)-n1
    return (r[y==1].sum()-n1*(n1+1)/2)/(n1*n0)
f=[0,2,3,4,5,6,7,8,9]  # exclude YOLO class id (discrete) from Gaussian; gate on it after
for c,det in [('huge_waves','best_realistic_v2.pt'),('night','best_realistic_v2.pt'),('huge_waves','old'),('night+rain','old'),('rain','old')]:
    R=[r for r in res if r[0]==c and r[1]==det]
    seeds=sorted({r[2] for r in R});tr={s for i,s in enumerate(seeds) if i%2==0}
    A=np.vstack([r[3] for r in R if r[2] in tr]);B=np.vstack([r[3] for r in R if r[2] not in tr])
    # candidates = boxes YOLO calls 'leader' (what the tracker would consume)
    A=A[A[:,1]==0];B=B[B[:,1]==0]
    yA=A[:,-1]==0;yB=(B[:,-1]==0)
    m1,S1=fit_gauss(A[yA][:,f]);m0,S0=fit_gauss(A[~yA][:,f]);p1=yA.mean()
    g=loglik(B[:,f],m1,S1)-loglik(B[:,f],m0,S0)   # log-likelihood ratio
    thr=np.log((1-p1)/p1)                         # 0-1 loss Bayes threshold
    # min-risk: accepting a false box costs lam_fa=5x rejecting a true one (KF can coast)
    thr_r=np.log(5*(1-p1)/p1)
    def rep(acc):
        fa=np.sum(acc&~yB);return f'false accepted={fa:6d} ({100*fa/max(acc.sum(),1):5.2f}% of accepted)  true rejected={np.sum(~acc&yB):6d} ({100*np.sum(~acc&yB)/yB.sum():5.2f}%)'
    print(f'\n{c} [{det}]  test leader-labelled boxes={len(B)}  truly leader={yB.mean()*100:.1f}%')
    print('  YOLO alone          :',rep(np.ones(len(B),bool)))
    print('  YOLO conf>=0.5      :',rep(B[:,0]>=0.5),' AUC(conf)=%.3f'%auc(yB,B[:,0]))
    print('  Bayes 0-1 loss      :',rep(g>thr),' AUC(LLR)=%.3f'%auc(yB,g))
    print('  Bayes min-risk λ=5  :',rep(g>thr_r))
