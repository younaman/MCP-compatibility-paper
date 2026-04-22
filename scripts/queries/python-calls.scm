;; ========================
;; Python 函数 & 方法调用
;; ========================

;; 方法调用：obj.method()
(call
  function: (attribute
    object: (_) @recv
    attribute: (identifier) @method)) @mcall

;; 普通函数调用：func()
(call
  function: (identifier) @func) @fcall



