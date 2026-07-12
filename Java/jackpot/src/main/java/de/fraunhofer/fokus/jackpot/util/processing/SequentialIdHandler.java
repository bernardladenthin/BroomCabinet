package de.fraunhofer.fokus.jackpot.util.processing;

@Deprecated
public interface SequentialIdHandler<T> {

    void process(final long id, final T t);
}
