;; ========================
;; Swift 调用（函数 & 方法）
;; ========================

;; 普通函数调用 foo(...)
(call_expression
  (simple_identifier) @func) @fcall

;; 方法调用 recv.method(...)
(call_expression
  (navigation_expression
    target: (_) @recv
    suffix: (navigation_suffix
      suffix: (simple_identifier) @method))) @mcall
