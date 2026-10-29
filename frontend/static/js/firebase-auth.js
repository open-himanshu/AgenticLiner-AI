/**
 * Official Real Firebase Authentication SDK Integration for AgenticLiner
 * Handles real Google Popup Login, Email/Password Creation, Real Email Verification, and Password Reset.
 */

// Firebase Configuration (Loaded from backend or env)
let auth = null;

function initFirebase(config) {
    if (!firebase.apps.length) {
        firebase.initializeApp(config);
    }
    auth = firebase.auth();
}

/**
 * Real Google Sign-In with Popup (opens accounts.google.com)
 */
async function signInWithGoogleReal(role = 'participant', department = 'School of AI') {
    if (!auth) {
        alert("Firebase is not initialized. Please configure your Firebase credentials.");
        return;
    }

    const provider = new firebase.auth.GoogleAuthProvider();
    provider.addScope('profile');
    provider.addScope('email');

    try {
        // This opens the REAL Google Login popup window from accounts.google.com
        const result = await auth.signInWithPopup(provider);
        const user = result.user;
        const idToken = await user.getIdToken();

        // Send real Google ID token to FastAPI backend
        const res = await fetch('/api/auth/firebase-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id_token: idToken,
                email: user.email,
                name: user.displayName || user.email.split('@')[0],
                role: role,
                department: department
            })
        });

        const data = await res.json();
        if (data.success && data.redirect_url) {
            window.location.href = data.redirect_url;
        } else {
            alert("Backend session creation failed: " + (data.detail || "Unknown error"));
        }
    } catch (error) {
        console.error("Google Auth Error:", error);
        if (error.code === 'auth/popup-closed-by-user') {
            console.log("User closed the Google popup window.");
        } else if (error.code === 'auth/unauthorized-domain') {
            alert("Error: localhost is not authorized in your Firebase Console. Go to Firebase Console > Authentication > Settings > Authorized Domains and add 'localhost'.");
        } else {
            alert("Google Sign-In Error: " + error.message);
        }
    }
}

/**
 * Real Firebase Email/Password Sign-Up with Verification Email
 */
async function signUpWithFirebaseEmail(email, password, fullName, role, department) {
    if (!auth) {
        alert("Firebase is not initialized.");
        return;
    }

    try {
        const userCredential = await auth.createUserWithEmailAndPassword(email, password);
        const user = userCredential.user;

        // Update Google display name
        await user.updateProfile({ displayName: fullName });

        // Send REAL verification email from Google/Firebase
        await user.sendEmailVerification();

        const idToken = await user.getIdToken();

        // Register in campus database
        const res = await fetch('/api/auth/firebase-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id_token: idToken,
                email: user.email,
                name: fullName,
                role: role,
                department: department
            })
        });

        const data = await res.json();
        alert("Verification email sent to " + email + ". Please check your inbox!");
        if (data.success && data.redirect_url) {
            window.location.href = data.redirect_url;
        }
    } catch (error) {
        console.error("Firebase Sign-Up Error:", error);
        alert("Registration failed: " + error.message);
    }
}

/**
 * Real Firebase Email/Password Login
 */
async function signInWithFirebaseEmail(email, password) {
    if (!auth) {
        alert("Firebase is not initialized.");
        return;
    }

    try {
        const userCredential = await auth.signInWithEmailAndPassword(email, password);
        const user = userCredential.user;
        const idToken = await user.getIdToken();

        const res = await fetch('/api/auth/firebase-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id_token: idToken,
                email: user.email,
                name: user.displayName || user.email.split('@')[0]
            })
        });

        const data = await res.json();
        if (data.success && data.redirect_url) {
            window.location.href = data.redirect_url;
        } else {
            alert("Login failed: " + (data.detail || "Invalid credentials"));
        }
    } catch (error) {
        console.error("Firebase Sign-In Error:", error);
        alert("Login failed: " + error.message);
    }
}

/**
 * Real Firebase Password Reset Email
 */
async function resetFirebasePassword(email) {
    if (!auth) {
        alert("Firebase is not initialized.");
        return;
    }

    try {
        await auth.sendPasswordResetEmail(email);
        alert("Password reset email sent to " + email + ". Please check your inbox!");
    } catch (error) {
        alert("Error sending password reset: " + error.message);
    }
}
