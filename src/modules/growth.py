import math

class Growth:
    def __init__(self, cfg, store):
        self.store = store
        self.weights = store.latest('growth', {}).get('weights', self.normalize(cfg))

    @staticmethod
    def normalize(weights):
        w = {k: float(weights[k]) for k in ('work','companion','learning')}
        if any(not math.isfinite(v) or v < 0 for v in w.values()) or sum(w.values()) <= 0:
            raise ValueError('权重应为有限非负数且总和 >0')
        total = sum(w.values())
        return {k:v/total for k,v in w.items()}

    def set(self, weights):
        self.weights = self.normalize(weights)
        return self.store.append('growth', weights=self.weights)
