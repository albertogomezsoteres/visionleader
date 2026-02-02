(define (domain campus-navigation)
  (:requirements :strips :typing :action-costs)
  
  (:types
    robot - object
    edificio - object
    planta - object
    tipo_conexion - object
  )

  (:predicates
    ;; Ubicación del robot
    (en ?r - robot ?b - edificio ?p - planta)
    
    ;; Recursos disponibles en ubicaciones
    (hay_ascensor ?b - edificio ?p - planta)
    (hay_escalera ?b - edificio ?p - planta)
    (hay_cafeteria ?b - edificio ?p - planta)
    (hay_gimnasio ?b - edificio ?p - planta)
    
    ;; Conexiones entre ubicaciones (relaciones binarias)
    (conectado ?b1 - edificio ?p1 - planta ?b2 - edificio ?p2 - planta ?tipo - tipo_conexion)
    
    ;; Estado de ascensores (para interacción humano-robot)
    (ascensor_disponible ?b - edificio ?p - planta)
    (humano_disponible)
    
    ;; Estado para escaleras (hace que sean menos preferibles)
    (escaleras_preparadas ?b - edificio ?p - planta)
    (escaleras_verificadas ?b - edificio ?p - planta)
  )
  
  (:action mover_edificio
    :parameters (?r - robot ?b_origen - edificio ?b_destino - edificio ?p - planta ?tipo - tipo_conexion)
    :precondition (and
      (en ?r ?b_origen ?p)
      (conectado ?b_origen ?p ?b_destino ?p ?tipo)
    )
    :effect (and
      (not (en ?r ?b_origen ?p))
      (en ?r ?b_destino ?p)
    )
  )
  
  (:action pedir_ayuda_ascensor
    :parameters (?r - robot ?b - edificio ?p - planta)
    :precondition (and
      (en ?r ?b ?p)
      (hay_ascensor ?b ?p)
      (humano_disponible)
    )
    :effect (and
      (ascensor_disponible ?b ?p)
    )
  )
  
  (:action usar_ascensor
    :parameters (?r - robot ?b - edificio ?p_origen - planta ?p_destino - planta ?tipo - tipo_conexion)
    :precondition (and
      (en ?r ?b ?p_origen)
      (hay_ascensor ?b ?p_origen)
      (ascensor_disponible ?b ?p_origen)
      (conectado ?b ?p_origen ?b ?p_destino ?tipo)
    )
    :effect (and
      (not (en ?r ?b ?p_origen))
      (en ?r ?b ?p_destino)
      (not (ascensor_disponible ?b ?p_origen))
    )
  )
  
  (:action verificar_seguridad_escaleras
    :parameters (?r - robot ?b - edificio ?p - planta)
    :precondition (and
      (en ?r ?b ?p)
      (hay_escalera ?b ?p)
    )
    :effect (and
      (escaleras_verificadas ?b ?p)
    )
  )
  
  (:action preparar_escaleras
    :parameters (?r - robot ?b - edificio ?p - planta)
    :precondition (and
      (en ?r ?b ?p)
      (hay_escalera ?b ?p)
      (escaleras_verificadas ?b ?p)
    )
    :effect (and
      (escaleras_preparadas ?b ?p)
      (not (escaleras_verificadas ?b ?p))
    )
  )
  
  (:action subir_escaleras
    :parameters (?r - robot ?b - edificio ?p_origen - planta ?p_destino - planta ?tipo - tipo_conexion)
    :precondition (and
      (en ?r ?b ?p_origen)
      (hay_escalera ?b ?p_origen)
      (escaleras_preparadas ?b ?p_origen)
      (conectado ?b ?p_origen ?b ?p_destino ?tipo)
    )
    :effect (and
      (not (en ?r ?b ?p_origen))
      (en ?r ?b ?p_destino)
      (not (escaleras_preparadas ?b ?p_origen))
    )
  )
  
  (:action bajar_escaleras
    :parameters (?r - robot ?b - edificio ?p_origen - planta ?p_destino - planta ?tipo - tipo_conexion)
    :precondition (and
      (en ?r ?b ?p_origen)
      (hay_escalera ?b ?p_origen)
      (escaleras_preparadas ?b ?p_origen)
      (conectado ?b ?p_origen ?b ?p_destino ?tipo)
    )
    :effect (and
      (not (en ?r ?b ?p_origen))
      (en ?r ?b ?p_destino)
      (not (escaleras_preparadas ?b ?p_origen))
    )
  )
)
