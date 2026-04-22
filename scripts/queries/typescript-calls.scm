;; ========================
;; TypeScript 函数 & 方法调用
;; ========================

;; 方法调用：obj.method()
(call_expression
  function: (member_expression
    object: (_) @recv
    property: (property_identifier) @method)) @mcall

;; 普通函数调用：foo()
(call_expression
  function: (identifier) @func) @fcall

;; new 构造函数调用：new Foo()
(new_expression
  constructor: (identifier) @func) @fcall
