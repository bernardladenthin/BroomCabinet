# PHP snippets

## Benchmark scripts (bundled as-is)

Third-party PHP micro-benchmark scripts, kept verbatim with their original
license/attribution:

| File | Author | License |
|------|--------|---------|
| [`php-benchmark.php`](php-benchmark.php) | Free-Webhosts.com (2006) | GPL |
| [`php-benchmark1.php`](php-benchmark1.php) | Alessandro Torrisi / Code24 BV (2010) | CC-BY |
| [`php-performance-benchmarks.php`](php-performance-benchmarks.php) | [Thiemo Mättig](http://maettig.com/) | Free to use (credit appreciated) |

Drop either on a PHP host and open it in a browser to time math/string/loop
operations.

PHP's own classic benchmark, `Zend/bench.php` (the `simple` / `mandel` /
`ackermann` / `heapsort` / `sieve` … harness), is **not bundled** — it ships
with the PHP source and carries no per-file header (it's covered by the PHP
License via the php-src repository). Use it upstream:
[php-src `Zend/bench.php`](https://github.com/php/php-src/blob/master/Zend/bench.php).

## List loaded Apache modules

```php
<?php
foreach (apache_get_modules() as $module) {
    echo "$module<br />";
}
```

## Check whether mod_rewrite is available

```php
<?php
if (!function_exists('apache_get_modules')) {
    phpinfo();
    exit;
}
$res = in_array('mod_rewrite', apache_get_modules())
    ? 'Module Available'
    : 'Module Unavailable';
echo apache_get_version() . '<br />mod_rewrite: ' . $res;
```

## Dump the PHP configuration

```php
<?php
phpinfo();
```
