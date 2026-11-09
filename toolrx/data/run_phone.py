import sys, time
sys.argv=['x','poc_ids.npy','poc_len.npy','800','16','96']
import train_poc_np as t
t.np.savez=lambda *a,**k: None
s=time.time()
t.main()
print('PHONE_RUN sec/step=%.3f total=%.1fs'%((time.time()-s)/800,(time.time()-s)),flush=True)
