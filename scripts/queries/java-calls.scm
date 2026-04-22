;; ========================
;; Java 方法 & 函数调用
;; ========================

;; 普通方法调用：foo()
(method_invocation
  name: (identifier) @func) @fcall

;; 带接收者的方法调用：obj.foo()
(method_invocation
  object: (_) @recv
  name: (identifier) @method) @mcall
