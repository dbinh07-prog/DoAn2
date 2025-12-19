a = input()
b = input()
m, n = len(a), len(b)
i, j = m - 1, n - 1
suf = [0] * (m + 1)
while i >= 0 and j >= 0:
    if a[i] == b[j]:
        suf[i] = suf[i + 1] + 1
        j -= 1
    else:
        suf[i] = suf[i + 1]
    i -= 1
left = 0
j = 0
l = 0
r = suf[0]
for i in range(m):
    if j < n and a[i] == b[j]:
        left += 1
        j += 1
    if left + suf[i + 1] > l + r:
        l = left
        r = suf[i + 1]
if l == r == 0:
    print('-')
elif l + r >= n:
    print(b)
else:
    print(b[: l] + b[n - r :])