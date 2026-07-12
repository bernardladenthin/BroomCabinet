# JavaScript snippets

## toCleanObject — convert a Nashorn object to a plain JS object

Recurses an object graph and rebuilds plain objects, leaving primitives
(number, string, boolean, null, undefined) untouched. Faster than
`JSON.parse(JSON.stringify(value))` when handing objects out of the Nashorn
engine (e.g. to MongoDB), since it only allocates for objects.

Source: [StackOverflow — put and get JSON object from Nashorn to MongoDB](http://stackoverflow.com/questions/35967012/put-and-get-json-object-from-nashorn-to-mongodb)

```js
define(function () {
    return {
        /**
         * Converts an object coming from Nashorn into a plain object. Only
         * creates new instances for objects; numbers, strings and booleans are
         * returned as-is.
         *
         * @param value the object to clean
         * @returns {Object} the clean object
         */
        toCleanObject: function (value) {
            switch (typeof value) {
                case "object":
                    var ret = {};
                    for (var key in value) {
                        ret[key] = this.toCleanObject(value[key]);
                    }
                    return ret;
                default: // number, string, boolean, null, undefined
                    return value;
            }
        }
    };
});
```
