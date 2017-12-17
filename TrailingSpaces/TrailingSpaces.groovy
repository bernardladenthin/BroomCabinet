new File('.').eachFileRecurse {
    boolean ok = true;
    if (it.name.startsWith (" ") ) {
        ok = false;
        println "startsWith space: " + it.name
    }
    if (it.name.endsWith (" ") ) {
        ok = false;
        println "endsWith space: " + it.name
    }
    if (it.name.contains ("  ") ) {
        ok = false;
        println "contains double spaces: " + it.name
    }
    
    if (ok) {
        println "ok: " + it.name
    }
}
