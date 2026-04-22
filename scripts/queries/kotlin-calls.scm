;; ========================
;; Kotlin 函数 & 方法调用
;; ========================

;; 普通函数调用：foo()
(call_expression
  (simple_identifier) @func) @fcall

;; 方法调用：recv.foo()
(call_expression
  (navigation_expression
    (simple_identifier) @recv
    (navigation_suffix
      (simple_identifier) @method))) @mcall

;; 带泛型的函数调用：foo<T>()
(call_expression
  (simple_identifier) @func
  (call_suffix
    (type_arguments))) @fcall

;; 带 lambda 的函数调用：foo { ... }
(call_expression
  (simple_identifier) @func
  (call_suffix
    (annotated_lambda) @lambda)) @fcall_with_lambda
