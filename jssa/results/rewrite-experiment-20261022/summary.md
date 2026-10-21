# Rewrite experiment summary

C = mean over seeds of min(t,180) if exact match else 180. Ratio = C_rep / C_A (log2 in brackets).

## exp1 AIME-2014-II-14
- A: 3/3 exact, C=1.80s, wall s0/s1/s2=1.8/1.7/1.9, path=alg, vars=2, eqs=2
- B: 3/3 exact, C=5.50s ratio 3.06 [+1.61], wall s0/s1/s2=5.7/5.2/5.7, path=num, vars=2, eqs=3
- C: 3/3 exact, C=46.77s ratio 26.00 [+4.70], wall s0/s1/s2=42.8/47.2/50.3, path=num, vars=14, eqs=14

## exp1 AIME-2016-I-06
- A: 3/3 exact, C=10.77s, wall s0/s1/s2=11.6/9.0/11.7, path=num, vars=3, eqs=2
- B: 3/3 exact, C=12.10s ratio 1.12 [+0.17], wall s0/s1/s2=10.9/10.1/15.3, path=num, vars=3, eqs=3
- C: 1/3 exact, C=135.81s ratio 12.61 [+3.66], wall s0/s1/s2=178.3/47.4/178.3, path=numnum+resc, vars=11, eqs=10

## exp1 AIME-2021-I-11
- A: 3/3 exact, C=16.38s, wall s0/s1/s2=17.3/17.1/14.8, path=num, vars=4, eqs=5
- B: 3/3 exact, C=19.64s ratio 1.20 [+0.26], wall s0/s1/s2=20.6/19.7/18.6, path=num, vars=4, eqs=10
- C: 3/3 exact, C=37.68s ratio 2.30 [+1.20], wall s0/s1/s2=41.2/37.2/34.6, path=num, vars=12, eqs=13

## exp1 HMMT-2013-FEB-GEO-05
- A: 3/3 exact, C=11.20s, wall s0/s1/s2=13.1/7.2/13.3, path=num, vars=3, eqs=2
- B: 3/3 exact, C=11.36s ratio 1.01 [+0.02], wall s0/s1/s2=13.1/7.7/13.3, path=num, vars=3, eqs=3
- C: 3/3 exact, C=65.84s ratio 5.88 [+2.56], wall s0/s1/s2=75.0/53.5/69.0, path=num, vars=9, eqs=8

## exp1 HMMT-2013-FEB-GEO-07
- A: 3/3 exact, C=6.21s, wall s0/s1/s2=3.9/7.0/7.8, path=num, vars=2, eqs=2
- B: 3/3 exact, C=8.08s ratio 1.30 [+0.38], wall s0/s1/s2=7.4/5.1/11.7, path=num, vars=2, eqs=3
- C: 3/3 exact, C=65.08s ratio 10.48 [+3.39], wall s0/s1/s2=55.3/20.8/119.2, path=num, vars=6, eqs=6

## exp1 HMMT-2017-FEB-GEO-10
- A: 3/3 exact, C=76.22s, wall s0/s1/s2=46.6/51.0/131.1, path=numnum+resc, vars=4, eqs=8
- B: 3/3 exact, C=105.77s ratio 1.39 [+0.47], wall s0/s1/s2=70.9/67.9/178.5, path=numnum+resc, vars=4, eqs=16
- C: 0/3 exact, C=180.00s ratio 2.36 [+1.24], wall s0/s1/s2=178.4/178.4/178.3, path=numnum+resc, vars=16, eqs=20

## exp2 AIME-2013-I-12
- A: 3/3 exact, C=11.34s, wall s0/s1/s2=11.3/11.7/11.0, path=num, vars=1, eqs=5
- R: 2/3 exact, C=131.26s ratio 11.58 [+3.53], wall s0/s1/s2=35.1/178.7/178.4, path=num, vars=6, eqs=7

## exp2 AIME-2015-II-07
- A: 3/3 exact, C=6.46s, wall s0/s1/s2=4.8/7.4/7.2, path=num, vars=1, eqs=12
- R: 3/3 exact, C=1.41s ratio 0.22 [-2.20], wall s0/s1/s2=1.1/1.6/1.6, path=alg, vars=2, eqs=5

## exp2 HMMT-2006-FEB-GEO-04
- A: 3/3 exact, C=1.26s, wall s0/s1/s2=1.0/1.5/1.3, path=, vars=0, eqs=4
- R: 3/3 exact, C=1.36s ratio 1.08 [+0.11], wall s0/s1/s2=1.0/1.6/1.5, path=alg, vars=1, eqs=4

## exp2 HMMT-2010-FEB-GEO-10
- A: 3/3 exact, C=5.08s, wall s0/s1/s2=1.9/11.6/1.8, path=, vars=0, eqs=2
- R: 3/3 exact, C=39.41s ratio 7.76 [+2.96], wall s0/s1/s2=35.0/43.2/40.0, path=num, vars=6, eqs=6

## exp2 HMMT-2016-FEB-GEO-03
- A: 3/3 exact, C=1.42s, wall s0/s1/s2=1.4/1.5/1.4, path=, vars=0, eqs=0
- R: 3/3 exact, C=3.41s ratio 2.40 [+1.26], wall s0/s1/s2=3.5/3.4/3.4, path=, vars=0, eqs=0

runs collected: 84/84
