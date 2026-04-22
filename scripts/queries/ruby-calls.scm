;; ========================
;; Ruby 方法 & 函数调用
;; ========================

;; 普通方法调用 foo()
(call
  method: (identifier) @func) @call

;; 带接收者的调用 obj.foo()
(call
  receiver: (_) @recv
  method: (identifier) @method) @mcall
