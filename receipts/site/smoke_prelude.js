/* Runs before the page's scripts. The page keeps its no-observer, no-animation
 * fallbacks, as in a test it must not wait on scrolling or frames; listeners are
 * counted so the smoke test can check they are attached. */
delete window.IntersectionObserver;
window.requestAnimationFrame = undefined;
const addListener = EventTarget.prototype.addEventListener;
EventTarget.prototype.addEventListener = function (type, listener, options) {
  this.__listeners = this.__listeners || {};
  this.__listeners[type] = (this.__listeners[type] || 0) + 1;
  return addListener.call(this, type, listener, options);
};
const dispatch = EventTarget.prototype.dispatchEvent;
EventTarget.prototype.dispatchEvent = function (event, init) {
  if (typeof event === "string") {
    event = new KeyboardEvent(event, { bubbles: true, cancelable: true, ...init });
  }
  return dispatch.call(this, event);
};
