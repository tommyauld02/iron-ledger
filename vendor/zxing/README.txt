The barcode reader. Downloaded, not written.

zxing-reader-3.1.4.js       the browser build of zxing-wasm 3.1.4 (dist/iife/reader/index.js
                            from the npm package), MIT licence — see LICENSE
zxing-reader-wasm-3.1.4.js  that package's dist/reader/zxing_reader.wasm, base64-encoded into a
                            script (window.IRON_LEDGER_ZXING_WASM) so it loads from disk with a
                            <script> tag, the way vendor/usda/foods.js does

The engine inside is zxing-cpp (https://github.com/zxing-cpp/zxing-cpp), Apache-2.0.

To update: download the new zxing-wasm package from npm into tools/.vendor-dl/ (ignored by
git), copy the iife reader build, base64 the reader .wasm the same way, and change ZX_JS and
ZX_WASM in iron-ledger.html. The version is in the file names, so the service worker's data
store fetches the new files rather than serving the old ones.
