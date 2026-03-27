// firestore-sync.js
// Real-time collaboration via Firestore

import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.7.0/firebase-app.js';
import {
    getFirestore,
    collection,
    doc,
    getDoc,
    setDoc,
    updateDoc,
    deleteDoc,
    onSnapshot,
    runTransaction,
    serverTimestamp,
    query,
    where,
    orderBy,
    enableIndexedDbPersistence
} from 'https://www.gstatic.com/firebasejs/10.7.0/firebase-firestore.js';
import { getAuth, onAuthStateChanged } from 'https://www.gstatic.com/firebasejs/10.7.0/firebase-auth.js';

let db = null;
let auth = null;
let currentUser = null;
let unsubscribers = [];

// Initialize Firestore
export function initFirestore(firebaseConfig) {
    const app = initializeApp(firebaseConfig);
    db = getFirestore(app);
    auth = getAuth(app);

    // Enable offline persistence
    enableIndexedDbPersistence(db).catch((err) => {
        if (err.code === 'failed-precondition') {
            console.warn('Persistence failed: multiple tabs open');
        } else if (err.code === 'unimplemented') {
            console.warn('Persistence not supported');
        }
    });

    // Track auth state
    onAuthStateChanged(auth, (user) => {
        currentUser = user;
        console.log('Auth state changed:', user?.uid);
    });

    return { db, auth };
}

// Get current user ID
export function getCurrentUserId() {
    return currentUser?.uid || null;
}

// ==========================================
// PROJECT SUBSCRIPTION
// ==========================================

export function subscribeToProject(projectId, callbacks) {
    const { onSegmentChange, onPresenceChange, onError } = callbacks;

    // Subscribe to all segments in project
    const segmentsQuery = query(
        collection(db, `projects/${projectId}/segments`),
        orderBy('paragraph_idx'),
        orderBy('segment_idx')
    );

    const unsubSegments = onSnapshot(segmentsQuery, (snapshot) => {
        snapshot.docChanges().forEach((change) => {
            const data = { id: change.doc.id, ...change.doc.data() };
            onSegmentChange(change.type, data);
        });
    }, onError);

    // Subscribe to presence
    const presenceQuery = collection(db, `projects/${projectId}/presence`);
    const unsubPresence = onSnapshot(presenceQuery, (snapshot) => {
        const users = [];
        snapshot.forEach((doc) => {
            users.push({ id: doc.id, ...doc.data() });
        });
        onPresenceChange(users);
    }, onError);

    unsubscribers.push(unsubSegments, unsubPresence);

    return () => {
        unsubSegments();
        unsubPresence();
    };
}

// ==========================================
// SEGMENT LOCKING (Atomic Transaction)
// ==========================================

export async function lockSegment(projectId, segmentId) {
    const userId = getCurrentUserId();
    if (!userId) throw new Error('Not authenticated');

    const segRef = doc(db, `projects/${projectId}/segments/${segmentId}`);

    await runTransaction(db, async (transaction) => {
        const segDoc = await transaction.get(segRef);

        if (!segDoc.exists()) {
            throw new Error('Segment not found');
        }

        const data = segDoc.data();

        // Check if locked by someone else
        if (data.locked_by && data.locked_by !== userId) {
            throw new Error(`Segment locked by ${data.locked_by_name || 'another user'}`);
        }

        // Lock it
        transaction.update(segRef, {
            locked_by: userId,
            locked_by_name: currentUser?.displayName || currentUser?.email,
            locked_at: serverTimestamp()
        });
    });

    return true;
}

export async function unlockSegment(projectId, segmentId) {
    const userId = getCurrentUserId();
    if (!userId) return;

    const segRef = doc(db, `projects/${projectId}/segments/${segmentId}`);

    await runTransaction(db, async (transaction) => {
        const segDoc = await transaction.get(segRef);

        if (!segDoc.exists()) return;

        const data = segDoc.data();

        // Only unlock if we own the lock
        if (data.locked_by === userId) {
            transaction.update(segRef, {
                locked_by: null,
                locked_by_name: null,
                locked_at: null
            });
        }
    });
}

// ==========================================
// SEGMENT UPDATES
// ==========================================

export async function updateSegmentText(projectId, segmentId, targetText, note = '') {
    const userId = getCurrentUserId();
    if (!userId) throw new Error('Not authenticated');

    const segRef = doc(db, `projects/${projectId}/segments/${segmentId}`);

    await updateDoc(segRef, {
        target_text: targetText,
        note: note,
        last_modified_by: userId,
        last_modified_by_name: currentUser?.displayName || currentUser?.email,
        last_modified_at: serverTimestamp()
    });
}

// ==========================================
// PRESENCE SYSTEM
// ==========================================

export async function setPresence(projectId, online = true, currentSegmentId = null) {
    const userId = getCurrentUserId();
    if (!userId) return;

    const presenceRef = doc(db, `projects/${projectId}/presence/${userId}`);

    if (online) {
        await setDoc(presenceRef, {
            name: currentUser?.displayName || currentUser?.email?.split('@')[0],
            email: currentUser?.email,
            online: true,
            last_seen: serverTimestamp(),
            current_segment: currentSegmentId
        }, { merge: true });
    } else {
        await deleteDoc(presenceRef);
    }
}

export async function updateCurrentSegment(projectId, segmentId) {
    const userId = getCurrentUserId();
    if (!userId) return;

    const presenceRef = doc(db, `projects/${projectId}/presence/${userId}`);
    await updateDoc(presenceRef, {
        current_segment: segmentId,
        last_seen: serverTimestamp()
    });
}

// ==========================================
// CLEANUP
// ==========================================

export function cleanup() {
    unsubscribers.forEach(unsub => unsub());
    unsubscribers = [];
}

// ==========================================
// UTILITY
// ==========================================

export async function getSegment(projectId, segmentId) {
    const segRef = doc(db, `projects/${projectId}/segments/${segmentId}`);
    const segDoc = await getDoc(segRef);

    if (!segDoc.exists()) return null;
    return { id: segDoc.id, ...segDoc.data() };
}

export { db, auth };
