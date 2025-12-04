"""
Práctica: Clasificación de CIFAR-10 con Redes Neuronales Convolucionales (CNN)
Este archivo contiene las funciones para completar las tareas CNN1, CNN2 y CNN3.
"""

import numpy as np
import matplotlib.pyplot as plt
from tensorflow import keras
from tensorflow.keras import layers, models
from tensorflow.keras.datasets import cifar10
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.initializers import HeNormal
import warnings
import sys
import os
from datetime import datetime
warnings.filterwarnings('ignore')


# =================================================================
#                    SISTEMA DE LOGGING
# =================================================================

class Tee:
    """
    Clase que permite escribir simultáneamente en consola y en archivo.
    """
    def __init__(self, *files):
        self.files = files
    
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    
    def flush(self):
        for f in self.files:
            f.flush()


def configurar_logging():
    """
    Configura el sistema de logging para capturar toda la salida en un archivo.
    Crea un archivo de log con timestamp en la carpeta 'logs'.
    """
    # Guardar referencias originales de stdout y stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # Crear carpeta logs si no existe
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Generar nombre de archivo con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"logs/cnn_cifar10_{timestamp}.log"
    
    # Abrir archivo de log
    log_file = open(log_filename, 'w', encoding='utf-8')
    
    # Redirigir stdout y stderr a consola y archivo
    sys.stdout = Tee(original_stdout, log_file)
    sys.stderr = Tee(original_stderr, log_file)
    
    print("=" * 80)
    print(f"LOG INICIADO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Archivo de log: {log_filename}")
    print("=" * 80)
    print()
    
    return log_file, log_filename, original_stdout, original_stderr


# =================================================================
#                    FUNCIONES AUXILIARES
# =================================================================

def cargar_y_preprocesar_cifar10():
    """
    Carga y preprocesa el dataset CIFAR-10.
    IMPORTANTE: Para CNNs, las imágenes mantienen su forma espacial (32x32x3).
    No se aplanan como en los MLP.
    
    Returns:
        tuple: (X_train, Y_train, X_test, Y_test) con datos preprocesados
    """
    # Cargar datos
    (X_train, y_train), (X_test, y_test) = cifar10.load_data()
    
    # Normalizar imágenes a [0, 1]
    X_train = X_train.astype('float32') / 255.0
    X_test = X_test.astype('float32') / 255.0
    
    # Convertir etiquetas a one-hot encoding
    Y_train = to_categorical(y_train, 10)
    Y_test = to_categorical(y_test, 10)
    
    print(f"Forma de X_train: {X_train.shape}")
    print(f"Forma de X_test: {X_test.shape}")
    print(f"Forma de Y_train: {Y_train.shape}")
    print(f"Forma de Y_test: {Y_test.shape}")
    
    return X_train, Y_train, X_test, Y_test


def probar_CNN(X_train, X_test, Y_train, Y_test, 
                filtros_conv=[16, 32], 
                kernel_size=3,
                capas_dense=[100],
                pooling='max',
                activacion='relu',
                epochs=50,
                batch_size=32,
                verbose=1,
                nombre_modelo="CNN"):
    """
    Declara, compila, entrena y evalúa un modelo CNN.
    
    Args:
        X_train, X_test: Datos de entrenamiento y prueba (sin aplanar)
        Y_train, Y_test: Etiquetas one-hot
        filtros_conv: Lista con número de filtros por capa convolucional
        kernel_size: Tamaño del kernel de convolución
        capas_dense: Lista con número de neuronas en capas densas (antes de la salida)
        pooling: Tipo de pooling ('max', 'avg', 'global_max', 'global_avg')
        activacion: Función de activación para capas convolucionales
        epochs: Número máximo de épocas
        batch_size: Tamaño del batch
        verbose: Verbosidad del entrenamiento
        nombre_modelo: Nombre para identificar el modelo
    
    Returns:
        tuple: (modelo, historial) - Modelo entrenado e historial de entrenamiento
    """
    # Crear modelo secuencial
    model = models.Sequential()
    
    # Añadir capas convolucionales según especificación
    for i, num_filtros in enumerate(filtros_conv):
        # Capa Conv2D
        if i == 0:
            # Primera capa: especificar input_shape
            model.add(layers.Conv2D(
                filters=num_filtros,
                kernel_size=(kernel_size, kernel_size),
                activation=activacion,
                kernel_initializer=HeNormal(),
                input_shape=(32, 32, 3),
                padding='same'
            ))
        else:
            # Capas siguientes: no especificar input_shape
            model.add(layers.Conv2D(
                filters=num_filtros,
                kernel_size=(kernel_size, kernel_size),
                activation=activacion,
                kernel_initializer=HeNormal(),
                padding='same'
            ))
        
        # Capa de Pooling
        if pooling == 'max':
            model.add(layers.MaxPooling2D(pool_size=(2, 2)))
        elif pooling == 'avg':
            model.add(layers.AveragePooling2D(pool_size=(2, 2)))
    
    # Aplanar para capas densas
    model.add(layers.Flatten())
    
    # Añadir capas densas ocultas
    for neuronas in capas_dense:
        model.add(layers.Dense(neuronas, activation='relu'))
    
    # Capa de salida
    model.add(layers.Dense(10, activation='softmax'))
    
    # Compilar modelo
    model.compile(
        optimizer='adam',
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    
    # Callbacks
    early_stopping = EarlyStopping(
        monitor='val_loss',
        patience=10,
        restore_best_weights=True,
        verbose=1
    )
    
    # Entrenar modelo
    history = model.fit(
        X_train, Y_train,
        batch_size=batch_size,
        epochs=epochs,
        validation_data=(X_test, Y_test),
        callbacks=[early_stopping],
        verbose=verbose
    )
    
    # Evaluar modelo
    test_loss, test_accuracy = model.evaluate(X_test, Y_test, verbose=0)
    print(f"\n[{nombre_modelo}] Precisión en test: {test_accuracy:.4f}")
    print(f"[{nombre_modelo}] Pérdida en test: {test_loss:.4f}")
    
    return model, history


def graficar_entrenamiento(history, titulo="Entrenamiento del Modelo"):
    """
    Grafica la evolución del entrenamiento (loss y accuracy).
    
    Args:
        history: Historial de entrenamiento de Keras
        titulo: Título de la gráfica
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    
    # Gráfica de pérdida
    ax1.plot(history.history['loss'], label='Train Loss')
    ax1.plot(history.history['val_loss'], label='Val Loss')
    ax1.set_title(f'{titulo} - Pérdida')
    ax1.set_xlabel('Época')
    ax1.set_ylabel('Pérdida')
    ax1.legend()
    ax1.grid(True)
    
    # Gráfica de precisión
    ax2.plot(history.history['accuracy'], label='Train Accuracy')
    ax2.plot(history.history['val_accuracy'], label='Val Accuracy')
    ax2.set_title(f'{titulo} - Precisión')
    ax2.set_xlabel('Época')
    ax2.set_ylabel('Precisión')
    ax2.legend()
    ax2.grid(True)
    
    plt.tight_layout()
    plt.show()


# =================================================================
#                    TAREA CNN1
# =================================================================

def tarea_CNN1():
    """
    Tarea CNN1: Definir, entrenar y evaluar un CNN sencillo con Keras.
    
    Arquitectura:
    - Bloque 1: Conv2D (16 filtros, 3x3, ReLU, He Normal) + MaxPooling2D (2x2)
    - Bloque 2: Conv2D (32 filtros, 3x3, ReLU, He Normal) + MaxPooling2D (2x2)
    - Capa Dense oculta: 100 neuronas
    - Capa de salida: Dense con softmax (10 clases)
    """
    print("=" * 60)
    print("TAREA CNN1: CNN Sencillo")
    print("=" * 60)
    
    # Cargar y preprocesar datos
    X_train, Y_train, X_test, Y_test = cargar_y_preprocesar_cifar10()
    
    # Definir y entrenar CNN según especificación
    CNN1, history1 = probar_CNN(
        X_train, X_test, Y_train, Y_test,
        filtros_conv=[16, 32],
        kernel_size=3,
        capas_dense=[100],
        pooling='max',
        epochs=100,
        batch_size=32,
        nombre_modelo="CNN1"
    )
    
    # Graficar resultados
    graficar_entrenamiento(history1, "CNN1 - Entrenamiento")
    
    return CNN1, history1


# =================================================================
#                    TAREA CNN2
# =================================================================

def tarea_CNN2():
    """
    Tarea CNN2: Ajustar el parámetro kernel_size de la CNN.
    
    Entrena varios modelos con diferentes tamaños de filtros (kernel_size)
    y analiza los resultados para seleccionar el mejor.
    """
    print("=" * 60)
    print("TAREA CNN2: Ajuste de kernel_size")
    print("=" * 60)
    
    # Cargar y preprocesar datos
    X_train, Y_train, X_test, Y_test = cargar_y_preprocesar_cifar10()
    
    # Probar diferentes tamaños de kernel
    kernel_sizes = [3, 5, 7]
    modelos = {}
    historiales = {}
    resultados = []
    
    for kernel_size in kernel_sizes:
        print(f"\n{'='*60}")
        print(f"Entrenando CNN con kernel_size={kernel_size}")
        print(f"{'='*60}")
        
        modelo, historial = probar_CNN(
            X_train, X_test, Y_train, Y_test,
            filtros_conv=[16, 32],
            kernel_size=kernel_size,
            capas_dense=[100],
            pooling='max',
            epochs=100,
            batch_size=32,
            nombre_modelo=f"CNN2_kernel{kernel_size}"
        )
        
        modelos[kernel_size] = modelo
        historiales[kernel_size] = historial
        
        # Evaluar y guardar resultados
        test_loss, test_accuracy = modelo.evaluate(X_test, Y_test, verbose=0)
        resultados.append({
            'kernel_size': kernel_size,
            'accuracy': test_accuracy,
            'loss': test_loss
        })
        
        # Graficar entrenamiento individual
        graficar_entrenamiento(historial, f"CNN2 - kernel_size={kernel_size}")
    
    # Comparar resultados
    print("\n" + "=" * 60)
    print("COMPARACIÓN DE RESULTADOS - TAREA CNN2")
    print("=" * 60)
    for res in resultados:
        print(f"kernel_size={res['kernel_size']}: "
              f"Accuracy={res['accuracy']:.4f}, Loss={res['loss']:.4f}")
    
    # Gráfica comparativa
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Comparar accuracy
    kernel_vals = [r['kernel_size'] for r in resultados]
    acc_vals = [r['accuracy'] for r in resultados]
    ax1.bar(kernel_vals, acc_vals, color=['blue', 'green', 'orange'])
    ax1.set_xlabel('kernel_size')
    ax1.set_ylabel('Accuracy')
    ax1.set_title('Comparación de Accuracy por kernel_size')
    ax1.set_ylim([0, 1])
    ax1.grid(True, alpha=0.3)
    
    # Comparar loss
    loss_vals = [r['loss'] for r in resultados]
    ax2.bar(kernel_vals, loss_vals, color=['blue', 'green', 'orange'])
    ax2.set_xlabel('kernel_size')
    ax2.set_ylabel('Loss')
    ax2.set_title('Comparación de Loss por kernel_size')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Seleccionar mejor modelo
    mejor_resultado = max(resultados, key=lambda x: x['accuracy'])
    print(f"\n✓ Mejor modelo: kernel_size={mejor_resultado['kernel_size']} "
          f"con accuracy={mejor_resultado['accuracy']:.4f}")
    
    return modelos, historiales, mejor_resultado


# =================================================================
#                    TAREA CNN3
# =================================================================

def tarea_CNN3():
    """
    Tarea CNN3: Optimizar la arquitectura de un CNN.
    
    Restricciones:
    - Máximo 32 filtros en capas Conv2D antes del primer MaxPooling2D
    - Máximo 128 filtros en el resto de capas Conv2D
    
    Se prueban diferentes arquitecturas, métodos de pooling y configuraciones
    para maximizar la tasa de acierto con recursos limitados.
    """
    print("=" * 60)
    print("TAREA CNN3: Optimización de Arquitectura CNN")
    print("=" * 60)
    
    # Cargar y preprocesar datos
    X_train, Y_train, X_test, Y_test = cargar_y_preprocesar_cifar10()
    
    # Definir diferentes arquitecturas a probar
    arquitecturas = [
        {
            'nombre': 'CNN3_A',
            'filtros_conv': [32, 64, 128],
            'kernel_size': 3,
            'pooling': 'max',
            'capas_dense': [100],
            'batch_size': 32
        },
        {
            'nombre': 'CNN3_B',
            'filtros_conv': [32, 64, 128],
            'kernel_size': 3,
            'pooling': 'avg',
            'capas_dense': [100],
            'batch_size': 32
        },
        {
            'nombre': 'CNN3_C',
            'filtros_conv': [32, 64, 128],
            'kernel_size': 3,
            'pooling': 'max',
            'capas_dense': [128, 64],
            'batch_size': 32
        },
        {
            'nombre': 'CNN3_D',
            'filtros_conv': [32, 64, 128, 128],
            'kernel_size': 3,
            'pooling': 'max',
            'capas_dense': [100],
            'batch_size': 64
        },
        {
            'nombre': 'CNN3_E',
            'filtros_conv': [32, 64, 128],
            'kernel_size': 5,
            'pooling': 'max',
            'capas_dense': [100],
            'batch_size': 32
        }
    ]
    
    modelos = {}
    historiales = {}
    resultados = []
    
    for arch in arquitecturas:
        # Verificar restricciones
        if arch['filtros_conv'][0] > 32:
            print(f"⚠️ {arch['nombre']}: Saltado - viola restricción (más de 32 filtros antes del primer pooling)")
            continue
        
        if any(f > 128 for f in arch['filtros_conv'][1:]):
            print(f"⚠️ {arch['nombre']}: Saltado - viola restricción (más de 128 filtros después del primer pooling)")
            continue
        
        print(f"\n{'='*60}")
        print(f"Entrenando: {arch['nombre']}")
        print(f"Filtros: {arch['filtros_conv']}, "
              f"Kernel: {arch['kernel_size']}, "
              f"Pooling: {arch['pooling']}, "
              f"Dense: {arch['capas_dense']}, "
              f"Batch: {arch['batch_size']}")
        print(f"{'='*60}")
        
        modelo, historial = probar_CNN(
            X_train, X_test, Y_train, Y_test,
            filtros_conv=arch['filtros_conv'],
            kernel_size=arch['kernel_size'],
            capas_dense=arch['capas_dense'],
            pooling=arch['pooling'],
            epochs=100,
            batch_size=arch['batch_size'],
            nombre_modelo=arch['nombre']
        )
        
        modelos[arch['nombre']] = modelo
        historiales[arch['nombre']] = historial
        
        # Evaluar y guardar resultados
        test_loss, test_accuracy = modelo.evaluate(X_test, Y_test, verbose=0)
        resultados.append({
            'nombre': arch['nombre'],
            'filtros_conv': arch['filtros_conv'],
            'kernel_size': arch['kernel_size'],
            'pooling': arch['pooling'],
            'capas_dense': arch['capas_dense'],
            'batch_size': arch['batch_size'],
            'accuracy': test_accuracy,
            'loss': test_loss
        })
        
        # Graficar entrenamiento individual
        graficar_entrenamiento(historial, f"{arch['nombre']} - Entrenamiento")
    
    # Comparar resultados
    print("\n" + "=" * 60)
    print("COMPARACIÓN DE RESULTADOS - TAREA CNN3")
    print("=" * 60)
    resultados_ordenados = sorted(resultados, key=lambda x: x['accuracy'], reverse=True)
    for res in resultados_ordenados:
        print(f"\n{res['nombre']}:")
        print(f"  Arquitectura: {res['filtros_conv']} filtros, "
              f"kernel={res['kernel_size']}, pooling={res['pooling']}")
        print(f"  Capas Dense: {res['capas_dense']}, batch_size={res['batch_size']}")
        print(f"  Accuracy: {res['accuracy']:.4f}, Loss: {res['loss']:.4f}")
    
    # Gráfica comparativa
    if resultados:
        fig, ax = plt.subplots(figsize=(12, 6))
        nombres = [r['nombre'] for r in resultados_ordenados]
        acc_vals = [r['accuracy'] for r in resultados_ordenados]
        
        bars = ax.barh(nombres, acc_vals, color='steelblue')
        ax.set_xlabel('Accuracy')
        ax.set_title('Comparación de Accuracy - Tarea CNN3')
        ax.set_xlim([0, 1])
        ax.grid(True, alpha=0.3, axis='x')
        
        # Añadir valores en las barras
        for i, (bar, acc) in enumerate(zip(bars, acc_vals)):
            ax.text(acc + 0.01, i, f'{acc:.4f}', va='center')
        
        plt.tight_layout()
        plt.show()
    
    # Seleccionar mejor modelo
    mejor_resultado = max(resultados, key=lambda x: x['accuracy'])
    print(f"\n{'='*60}")
    print(f"✓ MEJOR MODELO: {mejor_resultado['nombre']}")
    print(f"  Accuracy: {mejor_resultado['accuracy']:.4f}")
    print(f"  Arquitectura: {mejor_resultado['filtros_conv']} filtros, "
          f"kernel={mejor_resultado['kernel_size']}, pooling={mejor_resultado['pooling']}")
    print(f"  Capas Dense: {mejor_resultado['capas_dense']}")
    print(f"  Batch Size: {mejor_resultado['batch_size']}")
    print(f"{'='*60}")
    
    # Análisis y comentarios
    print("\n" + "=" * 60)
    print("ANÁLISIS Y COMENTARIOS - TAREA CNN3")
    print("=" * 60)
    print("""
    VENTAJAS DE CNN FRENTE A MLP:
    - Las CNNs preservan la información espacial de las imágenes
    - Los filtros convolucionales detectan características locales (bordes, texturas)
    - Comparten parámetros (menos parámetros que MLP completamente conectado)
    - Son más eficientes para datos con estructura espacial
    - Mejor capacidad de generalización para imágenes
    
    VENTAJAS DE MLP FRENTE A CNN:
    - Más simple de implementar y entender
    - Útil cuando no hay estructura espacial en los datos
    - Puede ser más rápido para datos pequeños y simples
    - No requiere ajuste de hiperparámetros de convolución
    
    OBSERVACIONES SOBRE ARQUITECTURAS:
    - Más capas convolucionales permiten detectar características de mayor nivel
    - MaxPooling suele funcionar mejor que AveragePooling para imágenes
    - Aumentar el número de filtros progresivamente mejora la capacidad del modelo
    - Capas Dense finales permiten combinar características extraídas
    - Batch size afecta la estabilidad del entrenamiento
    """)
    
    return modelos, historiales, mejor_resultado


# =================================================================
#                    BLOQUE PRINCIPAL
# =================================================================

if __name__ == "__main__":
    # Configurar logging al inicio
    log_file, log_filename, original_stdout, original_stderr = configurar_logging()
    
    try:
        # Funciones auxiliares relevantes para la evaluación, comentadas
        # test_MLP(...)
        
        # Cargar datos (común para todas las tareas)
        X_train, Y_train, X_test, Y_test = cargar_y_preprocesar_cifar10()
        
        # ============================================================
        # INSTRUCCIONES PARA EJECUTAR:
        # Para ejecutar una tarea, descomenta (quita el #) la línea 
        # correspondiente y comenta las demás.
        # Luego ejecuta: python cnn_cifar10.py
        # ============================================================
        
        # ============================================================
        # TAREA CNN1: CNN Sencillo
        # ============================================================
        # CNN1, history1 = tarea_CNN1()
        
        # ============================================================
        # TAREA CNN2: Ajuste de kernel_size
        # ============================================================
        # modelos_cnn2, historiales_cnn2, mejor_cnn2 = tarea_CNN2()
        
        # ============================================================
        # TAREA CNN3: Optimización de Arquitectura
        # ============================================================
        modelos_cnn3, historiales_cnn3, mejor_cnn3 = tarea_CNN3()
        
        print("\n" + "=" * 80)
        print(f"EJECUCIÓN COMPLETADA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Log guardado en: {log_filename}")
        print("=" * 80)
        
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"ERROR DURANTE LA EJECUCIÓN: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Error: {str(e)}")
        import traceback
        print("\nTraceback completo:")
        traceback.print_exc()
        print(f"\nLog guardado en: {log_filename}")
        print("=" * 80)
        raise
    
    finally:
        # Cerrar archivo de log y restaurar stdout/stderr
        log_file.close()
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        print(f"\n✓ Log guardado exitosamente en: {log_filename}")

