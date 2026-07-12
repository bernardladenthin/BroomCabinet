package de.fraunhofer.fokus.jackpot.interfaces;

public interface NotifyException {

    /**
     * Notify all observers an exception occurred.
     */
    void notifyException(final Exception e);
}
