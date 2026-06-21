// sim.js — shared SocketIO client. Connects once, and re-dispatches every
// tick as a plain DOM CustomEvent ("worldsim:tick") so individual page
// templates can listen without needing to know about socket.io directly.

(function () {
    if (typeof io === "undefined") {
        console.warn("[worldsim] socket.io client failed to load; live updates disabled.");
        return;
    }

    var socket = io();

    socket.on("connect", function () {
        console.log("[worldsim] connected");
    });

    socket.on("tick_update", function (summary) {
        document.dispatchEvent(new CustomEvent("worldsim:tick", { detail: summary }));
    });

    socket.on("disconnect", function () {
        console.log("[worldsim] disconnected — will retry automatically");
    });
})();
