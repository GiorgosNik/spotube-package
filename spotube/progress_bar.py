from tqdm import tqdm

class ProgressBar(tqdm):
    def update_to(self, b: int = 1, bsize: int = 1, tsize: [int] = None) -> None:
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)
