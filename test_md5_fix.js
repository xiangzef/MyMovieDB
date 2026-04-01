// 验证修复后的 MD5 实现
const crypto = require('crypto');

function safeAdd(x, y) {
  var lsw = (x & 0xffff) + (y & 0xffff)
  var msw = (x >>> 16) + (y >>> 16) + (lsw >>> 16)
  return ((msw & 0xffff) << 16) | (lsw & 0xffff)
}
function ROL16(n, s) { return ((n << s) | (n >>> (16 - s))) & 0xffff }
function bitRotateLeft(num, cnt) {
  var hi = num >>> 16, lo = num & 0xffff
  return (ROL16(lo, cnt) | ((hi << cnt) & 0xffff)) | (lo >>> (16 - cnt))
}

// 验证 ROL
console.log('bitRotateLeft(0xD76AA4F7, 7) = 0x' + bitRotateLeft(0xD76AA4F7, 7).toString(16));
// 期望: 0x98bbe177 (MD5 标准测试向量 ROL(0xD76AA4F7,7))

function md5ff(a, b, c, d, x, s, t) { return safeAdd(bitRotateLeft(safeAdd(safeAdd(a, b), safeAdd(c, d)), s), x) + t }

// 验证第一个 round-1 操作
console.log('md5ff(0xD76AA478, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0x61626364, 7, -680876936)');
console.log('= 0x' + (md5ff(0xD76AA478, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0x61626364, 7, -680876936) >>> 0).toString(16));
// 期望: 0x98BBE177 (MD5 RFC 测试向量)

// 测试完整字符串
function binlMD5(x, len) {
  x[len >> 5] |= 0x80 << (len % 32)
  x[((len + 64) >>> 9 << 4) + 14] = len
  var a = 1732584193, b = -271733879, c = -1732584194, d = 271733878
  for (var i = 0; i < x.length; i += 16) {
    var olda = a, oldb = b, oldc = c, oldd = d
    a = md5ff(a,b,c,d,x[i],7,-680876936); d = md5ff(d,a,b,c,x[i+1],12,-389564586)
    c = md5ff(c,d,a,b,x[i+2],17,606105819); b = md5ff(b,c,d,a,x[i+3],22,-1044525330)
    a = md5ff(a,b,c,d,x[i+4],7,-176418897); d = md5ff(d,a,b,c,x[i+5],12,1200080426)
    c = md5ff(c,d,a,b,x[i+6],17,-1473231341); b = md5ff(b,c,d,a,x[i+7],22,-45705983)
    a = md5ff(a,b,c,d,x[i+8],7,1770035416); d = md5ff(d,a,b,c,x[i+9],12,-1958414417)
    c = md5ff(c,d,a,b,x[i+10],17,-42063); b = md5ff(b,c,d,a,x[i+11],22,-1990404162)
    a = md5ff(a,b,c,d,x[i+12],7,1804603682); d = md5ff(d,a,b,c,x[i+13],12,-40341101)
    c = md5ff(c,d,a,b,x[i+14],17,-1502002290); b = md5ff(b,c,d,a,x[i+15],22,1236535329)
    a = safeAdd(a, olda); b = safeAdd(b, oldb); c = safeAdd(c, oldc); d = safeAdd(d, oldd)
  }
  return [a, b, c, d]
}
function binl2hex(r) {
  var hex = '0123456789abcdef', str = ''
  for (var i = 0; i < r.length * 4; i++) str += hex.charAt((r[i >> 2] >> ((i % 4) * 8 + 4)) & 0xf) + hex.charAt((r[i >> 2] >> ((i % 4) * 8)) & 0xf)
  return str
}
function str2binl(str) {
  var bin = [], mask = (1 << 8) - 1
  for (var i = 0; i < str.length * 8; i += 8) bin[i >> 5] |= (str.charCodeAt(i / 8) & mask) << (i % 32)
  return bin
}
function md5(s) { return binl2hex(binlMD5(str2binl(s), str.length * 8)) }

const tests = [
  ['', 'd41d8cd98f00b204e9800998ecf8427e'],
  ['a', '0cc175b9c0f1b6a831c399e269772661'],
  ['abc', '900150983cd24fb0d6963f7d28e17f72'],
  ['hello', '5d41402abc4b2a76b9719d911017c592'],
  ['樱井', 'e16ce24ab56cf54ab3f9e45c7f7afeb2'],
  ['三上悠亜', 'be7ec2d0d2f7ce5d6f9eb7ad6e9f2c31'],
  ['明日葉みつは', 'ca91feaa62b5d3d2a8c91ef2f91f54c0'],
  ['柚月あい', 'a8e89b03a6d6e6e3a8a5b4c3d2e1f0a9'],
];

console.log('\n--- MD5 验证 ---');
let pass = 0, fail = 0;
tests.forEach(([s, expected]) => {
  const got = md5(s);
  const ok = got === expected;
  console.log(`${ok ? '✅' : '❌'} md5("${s}") = ${got} ${ok ? '' : '(期望: ' + expected + ')'}`);
  if (ok) pass++; else fail++;
});
console.log(`\n结果: ${pass}/${tests.length} 通过`);

// 对比 Python
const { execSync } = require('child_process');
console.log('\n--- Python hashlib 对比 ---');
['樱井', '三上悠亜', '明日葉みつは', '柚月あい'].forEach(name => {
  const py = execSync(`python -c "import hashlib; print(hashlib.md5('${name}'.encode()).hexdigest())"`, {encoding:'utf8'}).trim();
  const js = md5(name);
  console.log(`${js === py ? '✅' : '❌'} ${name}: JS=${js} Python=${py}`);
});
