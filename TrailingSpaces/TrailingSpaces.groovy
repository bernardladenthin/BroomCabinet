new File('.').eachFileRecurse {
    boolean ok = true;
    if (it.name.startsWith (" ") ) {
        ok = false;
        println "nok: startsWith space: " + it.name
    }
    if (it.name.endsWith (" ") ) {
        ok = false;
        println "nok: endsWith space: " + it.name
    }
    if (it.name.contains ("  ") ) {
        ok = false;
        println "nok: contains double spaces: " + it.name
    }
    
    if (ok) {
        println "ok: " + it.name
    }
}
