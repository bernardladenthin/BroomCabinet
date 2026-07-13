<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Java Collection Matrix

## Most Commonly Known Collections

| Collection | Ordering | Random<br>Access | Key-Value<br>Pairs | Allows<br>Duplicates | Allows Null<br>Values | Thread Safe | Blocking<br>Operations | Upper<br>Bounds | Usage Scenarios |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| [ArrayList](http://download.oracle.com/javase/7/docs/api/java/util/ArrayList.html) | YES | YES | NO | YES | YES | NO | NO | NO | \* Default choice of List implementation<br>\* To store a bunch of things<br>\* Repetitions matters<br>\* Insertion order matters<br>\* Best implementation in case of huge lists which are read intensive<br>(elements are accessed more frequently than inserted deleted) |
| [HashMap](http://download.oracle.com/javase/7/docs/api/java/util/HashMap.html) | NO | YES | YES | NO | YES | NO | NO | NO | \* Default choice of Map implementation<br>\* Majorly used for simple in-memory caching purpose. |
| [Vector](http://download.oracle.com/javase/7/docs/api/java/util/Vector.html) | YES | YES | NO | YES | YES | YES | NO | NO | \* Historical implementation of List<br>\* A good choice for thread-safe implementation |
| [Hashtable](http://download.oracle.com/javase/7/docs/api/java/util/Hashtable.html) | NO | YES | YES | NO | NO | YES | NO | NO | \* Similar to HashMap<br>\* Do not allow null values or keys<br>\* Entire map is locked for thread safety |

## Most Talked About Collections

| Collection | Ordering | Random<br>Access | Key-Value<br>Pairs | Allows<br>Duplicates | Allows Null<br>Values | Thread Safe | Blocking<br>Operations | Upper<br>Bounds | Usage Scenarios |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| [HashSet](http://download.oracle.com/javase/7/docs/api/java/util/HashSet.html) | NO | YES | NO | NO | YES | NO | NO | NO | \* To store bunch of things<br>\* A very nice alternative for ArrayList if<br>\*\* Do not want repetitions<br>\*\* Ordering does not matter |
| [TreeSet](http://download.oracle.com/javase/7/docs/api/java/util/TreeSet.html) | YES | YES | NO | NO | NO | NO | NO | NO | \* To store bunch of things in sorted order<br>\* A very nice alternative for ArrayList if<br>\*\* Do not want repetitions<br>\*\* Sorted order |
| [LinkedList](http://download.oracle.com/javase/7/docs/api/java/util/LinkedList.html) | YES | NO | NO | YES | YES | NO | NO | NO | \* Sequential Access<br>\* Faster adding and deleting of elements<br>\* Slightly more memory than ArrayList<br>\* Add/Remove elements from both ends of the queue<br>\* Best alternative in case of huge lists which are more write intensive<br>(elements added / deleted are more frequent than reading elements) |
| [ArrayDeque](http://download.oracle.com/javase/7/docs/api/java/util/ArrayDeque.html) | YES | YES | NO | YES | NO | NO | NO | NO | \* Add/Remove elements from both ends in O(1)<br>\* Best used as a stack or queue — faster than Stack and LinkedList |
| [Stack](http://download.oracle.com/javase/7/docs/api/java/util/Stack.html) | YES | NO | NO | YES | YES | YES | NO | NO | \* Similar to a Vector<br>\* Last-In-First-Out implementation |
| [TreeMap](http://download.oracle.com/javase/7/docs/api/java/util/TreeMap.html) | YES | YES | YES | NO | NO | NO | NO | NO | \* A very nice alternative for HashMap if sorted keys are important |

## Special Purpose Collections

| Collection | Ordering | Random<br>Access | Key-Value<br>Pairs | Allows<br>Duplicates | Allows Null<br>Values | Thread Safe | Blocking<br>Operations | Upper<br>Bounds | Usage Scenarios |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| [WeakHashMap](http://download.oracle.com/javase/7/docs/api/java/util/WeakHashMap.html) | NO | YES | YES | NO | YES | NO | NO | NO | \* The keys that are not referenced will automatically become eligible for<br>garbage collection<br>\* Usually used for advanced caching techniques to store huge data and<br>want to conserve memory |
| [Arrays](http://download.oracle.com/javase/7/docs/api/java/util/Arrays.html) | YES | YES | NO | YES | YES | NO | NO | YES | \* A Utility class provided to manipulate arrays<br>\*\* Searching<br>\*\* Sorting<br>\*\* Converting to other Collection types such as a List |
| [Properties](http://download.oracle.com/javase/7/docs/api/java/util/Properties.html) | NO | YES | YES | NO | NO | YES | NO | NO | \* Properties are exactly same as the Hashtable<br>\* Keys and Values are String<br>\* Can be loaded from a input stream<br>\* Usually used to store application properties and configurations |

## Thread Safe Collections

| Collection | Ordering | Random<br>Access | Key-Value<br>Pairs | Allows<br>Duplicates | Allows Null<br>Values | Thread Safe | Blocking<br>Operations | Upper<br>Bounds | Usage Scenarios |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| [CopyOnWriteArrayList](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/CopyOnWriteArrayList.html) | YES | YES | NO | YES | YES | YES | NO | NO | \* A thread safe variant of ArrayList<br>\* Best use for<br>\*\* Small lists which are read intensive<br>\*\* requires thread-safety |
| [ConcurrentHashMap](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/ConcurrentHashMap.html) | NO | YES | YES | NO | NO | YES | NO | NO | \* A thread safe variant of Hashtable<br>\* Best use for<br>\*\* requires thread-safety<br>\*\* Better performance at high load due to a better locking mechanism |
| [ConcurrentSkipListMap](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/ConcurrentSkipListMap.html) | YES | YES | YES | NO | NO | YES | NO | NO | \* A thread safe variant of TreeMap<br>\* Best use for<br>\*\* requires thread-safety |
| [ConcurrentSkipListSet](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/ConcurrentSkipListSet.html) | YES | NO | NO | NO | NO | YES | NO | NO | \* A thread safe variant of TreeSet<br>\* Best use for<br>\*\* Do not want repetitions<br>\*\* Sorted order<br>\*\* Requires thread-safety |
| [CopyOnWriteArraySet](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/CopyOnWriteArraySet.html) | YES | YES | NO | NO | YES | YES | NO | NO | \* A thread-safe implementation of a Set<br>\* Best use for<br>\*\* Small lists which are read intensive<br>\*\* requires thread-safety<br>\*\* Do not want repetitions |
| [ConcurrentLinkedQueue](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/ConcurrentLinkedQueue.html) | YES | NO | NO | YES | NO | YES | NO | NO | \* A thread-safe unbounded FIFO queue<br>\* Best use for<br>\*\* Small lists<br>\*\* No random access<br>\*\* requires thread-safety |
| [ConcurrentLinkedDeque](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/ConcurrentLinkedDeque.html) | YES | NO | NO | YES | NO | YES | NO | NO | \* A thread-safe variant of LinkedList<br>\* Best use for<br>\*\* Small lists<br>\*\* No random access<br>\*\* Insertions, retrieval on both sides of the queue<br>\*\* requires thread-safety |

## Blocking Collections

| Collection | Ordering | Random<br>Access | Key-Value<br>Pairs | Allows<br>Duplicates | Allows Null<br>Values | Thread Safe | Blocking<br>Operations | Upper<br>Bounds | Usage Scenarios |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| [ArrayBlockingQueue](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/ArrayBlockingQueue.html) | YES | NO | NO | YES | NO | YES | YES | YES | \* Best use for Producer - Consumer type of scenarios with<br>\*\* Lower capacity bound<br>\*\* Predictable capacity<br>\* Has a bounded buffer. Space would be allocated during object creation |
| [LinkedBlockingQueue](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/LinkedBlockingQueue.html) | YES | NO | NO | YES | NO | YES | YES | YES | \* Best use for Producer - Consumer type of scenarios with<br>\*\* Large capacity bound<br>\*\* Unpredictable capacity<br>\* Upper bound is optional |
| [LinkedTransferQueue](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/LinkedTransferQueue.html) | YES | NO | NO | YES | NO | YES | YES | NO | \* Can be used in situations where the producers should wait for consumer<br>to receive elements. e.g. Message Passing |
| [PriorityBlockingQueue](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/PriorityBlockingQueue.html) | YES | NO | NO | YES | NO | YES | YES | NO | \* Best use for Producer - Consumer type of scenarios with<br>\*\* Large capacity bound<br>\*\* Unpredictable capacity<br>\*\* Consumer needs elements in sorted order |
| [LinkedBlockingDeque](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/LinkedBlockingDeque.html) | YES | NO | NO | YES | NO | YES | YES | YES | \* A Deque implementation of LinkedBlockingQueue<br>\*\* Can add elements at both head and tail |
| [SynchronousQueue](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/SynchronousQueue.html) | YES | NO | NO | YES | NO | YES | YES | NO | \* Both producer and consumer threads will have to wait for a handoff to<br>occur.<br>\* If there is no consumer waiting. The element is not added to the<br>collection. |
| [DelayQueue](http://download.oracle.com/javase/7/docs/api/java/util/concurrent/DelayQueue.html) | YES | NO | NO | YES | NO | YES | YES | NO | \* Similar to a normal LinkedBlockingQueue<br>\* Elements are implementations of Delayed interface<br>\* Consumer will be able to get the element only when it's delay has expired |

**Source:** [http://www.janeve.me/articles/which-java-collection-to-use](http://www.janeve.me/articles/which-java-collection-to-use)

---

## Type hierarchy

The same collections as the tables above, shown as a type hierarchy: the
interfaces (root `Iterable` / `Map`), the skeletal `Abstract*` classes, and the
concrete implementations, including the concurrent (`java.util.concurrent`) and
legacy types.

Relationship arrows: solid `<|--` = **extends** (class/interface inheritance),
dashed `<|..` = **implements** (a class realizing an interface).

### Collection: List & Set

```mermaid
classDiagram
    direction LR
    class Iterable { <<interface>> }
    class Collection { <<interface>> }
    class List { <<interface>> }
    class Set { <<interface>> }
    class SortedSet { <<interface>> }
    class NavigableSet { <<interface>> }
    class AbstractCollection { <<abstract>> }
    class AbstractList { <<abstract>> }
    class AbstractSequentialList { <<abstract>> }
    class AbstractSet { <<abstract>> }

    Iterable <|-- Collection
    Collection <|-- List
    Collection <|-- Set
    Set <|-- SortedSet
    SortedSet <|-- NavigableSet

    Collection <|.. AbstractCollection
    AbstractCollection <|-- AbstractList
    AbstractList <|-- AbstractSequentialList
    AbstractCollection <|-- AbstractSet
    List <|.. AbstractList
    Set <|.. AbstractSet

    AbstractList <|-- ArrayList
    AbstractList <|-- Vector
    Vector <|-- Stack
    AbstractSequentialList <|-- LinkedList
    List <|.. CopyOnWriteArrayList

    AbstractSet <|-- HashSet
    HashSet <|-- LinkedHashSet
    AbstractSet <|-- TreeSet
    NavigableSet <|.. TreeSet
    AbstractSet <|-- EnumSet
    AbstractSet <|-- CopyOnWriteArraySet
    NavigableSet <|.. ConcurrentSkipListSet

    class CopyOnWriteArrayList { concurrent }
    class CopyOnWriteArraySet { concurrent }
    class ConcurrentSkipListSet { concurrent }
    class Vector { legacy }
    class Stack { legacy }
```

### Queue & Deque

```mermaid
classDiagram
    direction LR
    class Collection { <<interface>> }
    class Queue { <<interface>> }
    class Deque { <<interface>> }
    class BlockingQueue { <<interface>> }
    class BlockingDeque { <<interface>> }
    class AbstractQueue { <<abstract>> }

    Collection <|-- Queue
    Queue <|-- Deque
    Queue <|-- BlockingQueue
    Deque <|-- BlockingDeque
    BlockingQueue <|-- BlockingDeque

    Queue <|.. AbstractQueue
    AbstractQueue <|-- PriorityQueue
    Deque <|.. ArrayDeque
    Deque <|.. LinkedList
    Queue <|.. ConcurrentLinkedQueue
    Deque <|.. ConcurrentLinkedDeque
    BlockingQueue <|.. ArrayBlockingQueue
    BlockingQueue <|.. LinkedBlockingQueue
    BlockingQueue <|.. PriorityBlockingQueue
    BlockingQueue <|.. DelayQueue
    BlockingQueue <|.. SynchronousQueue
    BlockingQueue <|.. LinkedTransferQueue
    BlockingDeque <|.. LinkedBlockingDeque

    class ConcurrentLinkedQueue { concurrent }
    class ConcurrentLinkedDeque { concurrent }
    class ArrayBlockingQueue { concurrent }
    class LinkedBlockingQueue { concurrent }
    class LinkedBlockingDeque { concurrent }
    class PriorityBlockingQueue { concurrent }
    class DelayQueue { concurrent }
    class SynchronousQueue { concurrent }
    class LinkedTransferQueue { concurrent }
```

`LinkedList` implements both `List` and `Deque`; `ArrayDeque` extends
`AbstractCollection` and implements `Deque`.

### Map

`Map` is **not** a `Collection` — it is a separate root hierarchy.

```mermaid
classDiagram
    direction LR
    class Map { <<interface>> }
    class SortedMap { <<interface>> }
    class NavigableMap { <<interface>> }
    class ConcurrentMap { <<interface>> }
    class ConcurrentNavigableMap { <<interface>> }
    class AbstractMap { <<abstract>> }
    class Dictionary { <<abstract>> }

    Map <|-- SortedMap
    SortedMap <|-- NavigableMap
    Map <|-- ConcurrentMap
    ConcurrentMap <|-- ConcurrentNavigableMap
    NavigableMap <|-- ConcurrentNavigableMap

    Map <|.. AbstractMap
    AbstractMap <|-- HashMap
    HashMap <|-- LinkedHashMap
    AbstractMap <|-- TreeMap
    NavigableMap <|.. TreeMap
    AbstractMap <|-- WeakHashMap
    AbstractMap <|-- IdentityHashMap
    AbstractMap <|-- EnumMap

    Dictionary <|-- Hashtable
    Map <|.. Hashtable
    Hashtable <|-- Properties

    AbstractMap <|-- ConcurrentHashMap
    ConcurrentMap <|.. ConcurrentHashMap
    AbstractMap <|-- ConcurrentSkipListMap
    ConcurrentNavigableMap <|.. ConcurrentSkipListMap

    class ConcurrentHashMap { concurrent }
    class ConcurrentSkipListMap { concurrent }
    class Dictionary { legacy }
    class Hashtable { legacy }
    class Properties { legacy }
```

### Notes

* **Legacy** (pre-Collections, Java 1.0/1.1, generally avoid): `Vector`, `Stack`,
  `Dictionary`, `Hashtable`, `Properties`, `Enumeration`. Prefer `ArrayList`,
  `ArrayDeque`, `HashMap`.
* **Concurrent** (`java.util.concurrent`): `ConcurrentHashMap`,
  `ConcurrentSkipListMap/Set`, `CopyOnWriteArrayList/Set`, the `BlockingQueue`
  family. Use these instead of `Collections.synchronizedXxx(...)` wrappers under
  contention.
* `EnumSet` / `EnumMap` are highly efficient specializations for enum keys.
* `Collections` and `Arrays` (utility classes, e.g. `Arrays` in the table above)
  and `Iterator` / `ListIterator` are part of the framework but are not
  collection types, so they are not shown in the hierarchy.
