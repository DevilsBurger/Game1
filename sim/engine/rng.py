# -*- coding: utf-8 -*-
"""
결정론 난수원 (C# 포팅 1:1 재현용). 파이썬 random.Random(메르센 트위스터)을 대체한다.

사양 (반드시 동일하게 포팅):
  state: uint64. seed → splitmix64로 초기화 (0이 되지 않도록). splitmix64(x): x += 0x9E3779B97F4A7C15; z=x; z=(z^(z>>30))*0xBF58476D1CE4E5B9; z=(z^(z>>27))*0x94D049BB133111EB; z^(z>>31)
  next_u64(): xorshift64*  x ^= x>>12; x ^= x<<25; x ^= x>>27; return (x * 0x2545F4914F6CDD1D) mod 2^64
  random():   (next_u64() >> 11) * 2^-53  → [0,1) double (53비트)
  randrange(n): next_u64() % n  (n>0, uint64 모듈로)
  choice(seq): seq[randrange(len)]
  shuffle(list): Fisher–Yates: for i in n-1..1: j = randrange(i+1); swap(i, j)
  sample(seq, k): copy → for i in 0..k-1: j = i + randrange(n-i); swap(i,j) → 앞 k개
  uniform(a,b): a + (b-a)*random()
모든 연산은 IEEE 754 binary64, 초월함수 없음. C#은 double/ulong, unchecked 산술, Burst fast-math 금지.
"""
MASK = (1 << 64) - 1


def splitmix64(x):
    x = (x + 0x9E3779B97F4A7C15) & MASK
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return (z ^ (z >> 31)) & MASK


class Rng:
    __slots__ = ("s",)

    def __init__(self, seed=0):
        s = splitmix64(int(seed) & MASK)
        self.s = s if s != 0 else 0x9E3779B97F4A7C15

    def next_u64(self):
        x = self.s
        x ^= (x >> 12)
        x ^= (x << 25) & MASK
        x ^= (x >> 27)
        self.s = x
        return (x * 0x2545F4914F6CDD1D) & MASK

    def random(self):
        return (self.next_u64() >> 11) * (1.0 / 9007199254740992.0)

    def randrange(self, n):
        if n <= 0:
            raise ValueError("randrange: n must be > 0")
        return self.next_u64() % n

    def choice(self, seq):
        return seq[self.randrange(len(seq))]

    def shuffle(self, lst):
        for i in range(len(lst) - 1, 0, -1):
            j = self.randrange(i + 1)
            lst[i], lst[j] = lst[j], lst[i]

    def sample(self, seq, k):
        arr = list(seq)
        n = len(arr)
        if k > n:
            raise ValueError("sample larger than population")
        for i in range(k):
            j = i + self.randrange(n - i)
            arr[i], arr[j] = arr[j], arr[i]
        return arr[:k]

    def uniform(self, a, b):
        return a + (b - a) * self.random()

    def getstate(self):
        return self.s


def known_answers(seed=1, n=5):
    r = Rng(seed)
    return {"seed": seed, "u64": [r.next_u64() for _ in range(n)], "random": [Rng(seed).random() for _ in range(1)][0]}
