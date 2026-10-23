# Imagen Debian 13 para Google Cloud con Packer

Construye una imagen **Debian 13 x86-64** desde la familia oficial `debian-13` del proyecto `debian-cloud`. La plantilla crea una VM temporal y ejecuta un **playbook Ansible seleccionable** para instalar y configurar paquetes. Después reinicia, verifica el acceso SSH y los paquetes de integración, limpia identificadores y genera la imagen en tu proyecto. El playbook predeterminado actualiza los paquetes e instala `ca-certificates` y `curl`.

El resultado tiene un nombre como `debian-13-base-20261012-210000`, pertenece a `debian-13-base` y queda registrado en `manifest.json`. El inventario de paquetes, kernel y fecha de construcción se guarda dentro de `/etc/golden-image/`.

## Archivos

- `main.pkr.hcl`: valores calculados, instrucciones de construcción, provisioners y manifest.
- `variables.pkr.hcl`: declaración, tipos, valores predeterminados y validación de variables.
- `providers.pkr.hcl`: versión de Packer, plugins requeridos y builder de Google Compute.
- `debian13.example.pkrvars.hcl`: valores para adaptar al proyecto.
- `ansible/playbooks/base.yml`: actualización e instalación de paquetes con Ansible.
- `ansible/playbooks/web.yml`: ejemplo que importa la base e instala Nginx.
- `ansible/playbooks/finalize.yml`: comprobaciones después del reinicio, inventario y limpieza final.
- `.github/workflows/validate.yml`: validación automática de Packer y playbooks.
- `.github/workflows/build-image.yml`: construcción manual en GCP desde GitHub Actions.
- `requirements-ci.txt`: versión de Ansible del controlador de CI.
- `tests/`: pruebas de variables y nombres de Packer, inputs y resumen de GitHub Actions.

## Requisitos

- Packer 1.14 o superior y Google Cloud CLI (`gcloud`).
- `ansible-playbook` en el PATH del equipo que ejecuta Packer; usar `ansible-core` 2.18 o superior compatible con el Python de Debian 13. Ansible se ejecuta en ese equipo y utiliza Python 3 en la VM; no se instala Ansible dentro de la imagen.
- Proyecto GCP con facturación, cuota de Compute Engine y una VPC/subred existentes.
- APIs `compute.googleapis.com`, `oslogin.googleapis.com` e `iap.googleapis.com` habilitadas para la configuración predeterminada.
- Con IAP, una regla de ingreso TCP/22 desde `35.235.240.0/20` dirigida al tag `packer-build`.
- **Con IAP la VM no tiene IP pública: necesita Cloud NAT, un proxy previamente configurado u otra salida a los repositorios APT. IAP proporciona acceso SSH, no salida a Internet. Private Google Access por sí solo no cubre repositorios públicos de Debian.**

La plantilla utiliza OS Login. La identidad que ejecuta Packer debe poder crear/eliminar VMs y discos, crear imágenes y administrar metadatos. Como referencia operativa, revisar `roles/compute.instanceAdmin.v1` y `roles/compute.storageAdmin`; se pueden sustituir por un rol personalizado con los permisos necesarios. También necesita `roles/compute.osAdminLogin` para sudo y `roles/iap.tunnelResourceAccessor` para IAP. Para Shared VPC, revisar `roles/compute.networkUser` sobre la subred/proyecto host. Un usuario de otra organización puede necesitar `roles/compute.osLoginExternalUser` a nivel de organización.

La VM temporal se crea sin service account. La autenticación de Packer utiliza las credenciales del ejecutor; no se copian credenciales a la imagen.

Fuentes: [autenticación del plugin](https://developer.hashicorp.com/packer/integrations/hashicorp/googlecompute/latest), [roles de Compute Engine](https://docs.cloud.google.com/iam/docs/roles-permissions/compute) y [configuración de OS Login](https://docs.cloud.google.com/compute/docs/oslogin/set-up-oslogin).

## Configuración inicial

Desde este directorio:

```sh
cp debian13.example.pkrvars.hcl debian13.pkrvars.hcl
```

Editar `project_id`, `zone`, `network` y `subnetwork`. Si la red tiene subredes personalizadas, indicar la subred; su región debe coincidir con la zona. Los valores `default` y `us-central1-a` son ejemplos, no infraestructura creada por la plantilla.

Autenticarse con la misma identidad para `gcloud` (túnel IAP) y ADC (Packer):

```sh
gcloud auth login
gcloud auth application-default login
```

Si `GOOGLE_APPLICATION_CREDENTIALS` está definido, puede tener precedencia sobre ADC; comprobar que corresponde a la identidad prevista.

Si faltan APIs, un administrador con permisos puede habilitarlas:

```sh
gcloud services enable compute.googleapis.com oslogin.googleapis.com iap.googleapis.com \
  --project=MI_PROYECTO
```

Si falta el acceso de IAP en la VPC elegida, crear la regla ajustando proyecto y red. En Shared VPC, usar el proyecto host:

```sh
gcloud compute firewall-rules create allow-packer-iap-ssh \
  --project=MI_PROYECTO \
  --network=MI_RED \
  --direction=INGRESS \
  --action=ALLOW \
  --rules=tcp:22 \
  --source-ranges=35.235.240.0/20 \
  --target-tags=packer-build
```

La VPC, NAT, firewall, APIs e IAM se administran fuera de esta plantilla. [Configuración oficial de IAP](https://docs.cloud.google.com/iap/docs/using-tcp-forwarding).

## Validar y construir

Ejecutar Packer sobre el directorio (`.`) para cargar juntos `main.pkr.hcl`, `variables.pkr.hcl` y `providers.pkr.hcl`.

La ruta de plugins local mantiene la instalación dentro del directorio:

```sh
export PACKER_PLUGIN_PATH="$PWD/.packer.d/plugins"
packer init .
packer fmt -check .
packer validate -var-file=debian13.pkrvars.hcl .
packer build -var-file=debian13.pkrvars.hcl .
```

## Elegir un playbook

Se puede indicar en `debian13.pkrvars.hcl`:

```hcl
ansible_playbook_file = "ansible/playbooks/web.yml"
image_family         = "debian-13-web"
```

También se puede seleccionar por ejecución. Estos dos ejemplos construyen variantes diferentes:

```sh
packer build -var-file=debian13.pkrvars.hcl \
  -var='ansible_playbook_file=ansible/playbooks/base.yml' \
  -var='image_family=debian-13-base' .

packer build -var-file=debian13.pkrvars.hcl \
  -var='ansible_playbook_file=ansible/playbooks/web.yml' \
  -var='image_family=debian-13-web' .
```

Se admiten rutas absolutas a playbooks externos. Las rutas relativas se interpretan desde el directorio donde se ejecuta Packer. Usar familias distintas permite publicar variantes independientes.

Packer genera el inventario con el grupo `packer` y el host `image`. Los playbooks propios deben utilizar `hosts: packer`, `hosts: image` o `hosts: all`. El provisioner utiliza el usuario real del comunicador de Packer, incluyendo el usuario determinado por OS Login, y habilita `become` para instalar paquetes. El proxy local de Packer transporta la conexión de Ansible por el mismo comunicador que utiliza IAP; no requiere que Ansible alcance directamente la IP privada.

Para ejecutar varios playbooks en orden, crear un playbook de entrada que los importe y pasarlo en `ansible_playbook_file`. `web.yml` muestra este patrón. Por ejemplo:

```yaml
---
- name: Preparar la base
  ansible.builtin.import_playbook: base.yml
- name: Configurar la aplicación
  ansible.builtin.import_playbook: aplicacion.yml
```

Los imports relativos se resuelven desde el playbook que los contiene. Los playbooks seleccionados controlan sus paquetes; no es obligatorio importar `base.yml`. Deben conservar SSH y los agentes de Google que comprueba la finalización, y dejar los reinicios a Packer.

## Pasar variables y argumentos a Ansible

En `debian13.pkrvars.hcl`:

```hcl
ansible_extra_arguments = ["--extra-vars", "@/ruta/variables.yml"]
```

Ejemplo de `/ruta/variables.yml` para modificar los paquetes del playbook base:

```yaml
base_packages:
  - ca-certificates
  - curl
  - jq
```

También se pueden pasar argumentos como `--tags` o `--skip-tags`. Cada argumento ocupa un elemento de la lista; Packer no los interpreta con un shell. Si un playbook requiere roles o collections externos, instalarlos en el entorno del controlador antes de construir, por ejemplo con `ansible-galaxy install -r /ruta/requirements.yml`.

Packer ejecuta el playbook seleccionado, reinicia la VM y ejecuta siempre `ansible/playbooks/finalize.yml`. Este último espera la conexión, comprueba Debian 13, los paquetes críticos y SSH, registra el inventario y limpia APT, el identificador de máquina, las claves de host SSH y la semilla aleatoria. Después se captura la imagen sin otro reinicio. `ansible_extra_arguments` solo se aplica al playbook seleccionado, para que opciones como `--tags` o `--skip-tags` no omitan la finalización. [Provisioner oficial de Ansible](https://developer.hashicorp.com/packer/integrations/hashicorp/ansible/latest/components/provisioner/ansible), [espera de conexión](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/wait_for_connection_module.html).

## Comprobaciones locales

`packer build` crea recursos facturables en GCP y deja una imagen que genera cargos de almacenamiento. Packer elimina normalmente la VM y el disco temporales al terminar; una interrupción abrupta puede dejar recursos para revisar. `validate` comprueba la configuración, pero no demuestra que IAM, red o cuotas permitan completar el build.

Para probar con los valores de ejemplo, sin construir:

```sh
packer validate -var-file=debian13.example.pkrvars.hcl .
ansible-playbook --syntax-check -i 'packer,' ansible/playbooks/base.yml
ansible-playbook --syntax-check -i 'packer,' ansible/playbooks/web.yml
ansible-playbook --syntax-check -i 'packer,' ansible/playbooks/finalize.yml
```

## Pruebas automatizadas

Ejecutar desde la raíz del repositorio con Python 3.10 o superior y Packer instalado:

```sh
export PACKER_PLUGIN_PATH="$PWD/.packer.d/plugins"
packer init .
python3 -m unittest discover -s tests -v
```

Las pruebas utilizan `unittest`, incluido en Python. Comprueban las validaciones reales de variables con `packer validate`, el nombre de la imagen con `packer console` y los helpers de GitHub Actions con archivos y variables de entorno aislados. Cubren familias válidas e inválidas, límites de longitud, proyectos vacíos, playbooks inexistentes, argumentos JSON y rutas fuera del repositorio, incluidas rutas mediante enlaces simbólicos. El resumen debe utilizar el último build del manifest y conservar el contenido previo.

No requieren credenciales ni crean recursos en GCP. Si faltan los plugins de Google Compute o Ansible en `.packer.d/plugins`, los casos de validación de variables se marcan como omitidos localmente; ejecutar `packer init .` para habilitarlos. Las demás pruebas se pueden ejecutar sin descargar plugins. GitHub Actions instala los plugins antes de ejecutar la suite y considera un error que falten.

Estas pruebas verifican configuración y lógica local; comprobar el arranque, los servicios y el resultado del provisionamiento requiere construir y arrancar una VM. `packer validate` comprueba la plantilla, mientras que `-syntax-only` comprueba únicamente su sintaxis. [Documentación de Packer validate](https://developer.hashicorp.com/packer/docs/commands/validate).

## Alternativa con IP pública

Si no existe NAT y las políticas del proyecto permiten IP externa, establecer `use_iap = false` en el archivo de variables. Packer utilizará SSH directo. La red debe permitir TCP/22 desde la IP pública del ejecutor hacia `packer-build`, y salida a los repositorios APT. OS Login sigue habilitado; no se necesita permiso IAP para esta modalidad.

## Fijar la imagen de origen

Por defecto, cada build toma la última imagen no deprecada de `debian-13`. Para registrar y fijar una versión:

```sh
gcloud compute images describe-from-family debian-13 \
  --project=debian-cloud \
  --format='value(name)'
```

Copiar el nombre en `source_image` dentro de `debian13.pkrvars.hcl`. El plugin da prioridad a ese nombre sobre la familia. Los paquetes APT se actualizan al construir: fijar la imagen de origen no fija las versiones de los repositorios.

## Utilizar la imagen

El nombre concreto aparece al finalizar Packer y en `manifest.json`. Para producción, utilizar ese nombre permite controlar qué versión se despliega. La familia selecciona la última imagen disponible de esa familia.

Ejemplo de VM con IP privada; ajustar subred y conectividad. Este comando crea una VM adicional:

```sh
gcloud compute instances create debian13-app \
  --project=MI_PROYECTO \
  --zone=us-central1-a \
  --machine-type=e2-standard-2 \
  --subnet=MI_SUBRED \
  --no-address \
  --no-service-account \
  --tags=packer-build \
  --metadata=enable-oslogin=TRUE \
  --image=NOMBRE_DE_IMAGEN_GENERADA \
  --image-project=MI_PROYECTO
```

Los metadatos y tags de la VM de construcción no se heredan como configuración de las nuevas VMs. OS Login se habilita también al desplegar. El tag del ejemplo reutiliza el acceso IAP de construcción; para producción, adaptar tags y reglas a la red de la aplicación.

La limpieza de claves SSH depende del entorno invitado oficial de Google, que se conserva y genera nuevas claves de host en el primer arranque. Los paquetes y servicios de aplicación dependen del playbook seleccionado. [Funciones del guest agent](https://docs.cloud.google.com/compute/docs/images/guest-agent-functions).

Referencias de configuración: [builder googlecompute](https://developer.hashicorp.com/packer/integrations/hashicorp/googlecompute/latest/components/builder/googlecompute), [provisioner shell](https://developer.hashicorp.com/packer/docs/provisioners/shell) y [imágenes Debian admitidas en GCP](https://docs.cloud.google.com/compute/docs/images/os-details#debian).

## GitHub Actions

Los workflows quedan listos para ejecutarse al subir este directorio a un repositorio GitHub. La validación corre en pull requests, pushes a `main` y por lanzamiento manual; si la rama principal tiene otro nombre, ajustar `push.branches` en `validate.yml`. Este workflow instala los plugins y ejecuta `packer validate` y comprueba todos los playbooks incluidos, también el de finalización. No requiere credenciales de GCP.

La construcción se lanza manualmente desde **Actions → Build Debian 13 GCP image → Run workflow** sobre la rama predeterminada. Instala dependencias, valida el playbook seleccionado y el de finalización, autentica en GCP, construye y publica el manifest y un resumen con el nombre de la imagen. Las construcciones se serializan para permitir completar el build activo y su limpieza.

### Variables de GitHub

Crear el environment `gcp-images` en **Settings → Environments**. Configurar allí, o como variables del repositorio en **Settings → Secrets and variables → Actions → Variables**:

| Variable | Obligatoria | Valor / ejemplo |
| --- | --- | --- |
| `GCP_PROJECT_ID` | Sí | Proyecto que construye y almacena la imagen. |
| `GCP_WIF_PROVIDER` | Sí | `projects/123456789/locations/global/workloadIdentityPools/github/providers/github`. |
| `GCP_SERVICE_ACCOUNT` | Sí | `packer-ci@mi-proyecto.iam.gserviceaccount.com`. |
| `GCP_ZONE` | No | Predeterminado: `us-central1-a`. |
| `GCP_NETWORK` | No | Predeterminado: `default`. |
| `GCP_SUBNETWORK` | Para redes con subredes personalizadas | Nombre o URL de la subred con salida a repositorios. |
| `GCP_NETWORK_PROJECT_ID` | Para Shared VPC | Proyecto host. |
| `GCP_MACHINE_TYPE` | No | Predeterminado: `e2-standard-2`. |

Los valores del environment prevalecen sobre los del repositorio. CI pasa los valores con `PKR_VAR_*`; no necesita el archivo local `debian13.pkrvars.hcl`. Los identificadores de WIF y service account son configuración; este flujo utiliza OIDC y no necesita una clave JSON persistente en GitHub Secrets.

### Configuración de GCP para CI

Crear una service account para Packer y un Workload Identity Pool/Provider que confíe en el emisor OIDC de GitHub (`https://token.actions.githubusercontent.com`). Mapear al menos `google.subject=assertion.sub` y `attribute.repository=assertion.repository`.

La condición del provider debe limitar el acceso al repositorio y a su rama predeterminada. Por ejemplo, para `MI_ORG/MI_REPO` con rama `main`:

```text
assertion.repository == 'MI_ORG/MI_REPO' && assertion.ref == 'refs/heads/main'
```

Conceder `roles/iam.workloadIdentityUser` **sobre la service account** al principal del repositorio. Comando de referencia para un administrador; ajustar los valores:

```sh
gcloud iam service-accounts add-iam-policy-binding \
  packer-ci@MI_PROYECTO.iam.gserviceaccount.com \
  --project=MI_PROYECTO \
  --role=roles/iam.workloadIdentityUser \
  --member='principalSet://iam.googleapis.com/projects/NUMERO_PROYECTO_POOL/locations/global/workloadIdentityPools/MI_POOL/attribute.repository/MI_ORG/MI_REPO'
```

Asignar a esa service account los permisos de construcción, imágenes, OS Login administrativo e IAP descritos en los requisitos iniciales. Habilitar además `iamcredentials.googleapis.com` y `sts.googleapis.com` para la federación. La identidad de CI es la que construye; la VM temporal continúa sin service account adjunta.

El runner hospedado de GitHub accede mediante IAP. Mantener la regla TCP/22 desde `35.235.240.0/20` hacia `packer-build` y proporcionar NAT u otra salida a los repositorios en la subred. No hace falta abrir SSH a las IP de los runners. Los archivos temporales `gha-creds-*.json` quedan excluidos de Git y el único archivo publicado como artefacto es `manifest.json`.

Fuentes: [federación para pipelines](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines) y [autenticación de Google para GitHub Actions](https://github.com/google-github-actions/auth).

### Inputs de construcción

| Input | Uso |
| --- | --- |
| `playbook` | Ruta dentro del repositorio; predeterminado `ansible/playbooks/base.yml`. |
| `image_family` | Familia destino; usar `debian-13-web` para la variante web. |
| `ansible_extra_arguments` | Lista JSON de strings; predeterminado `[]`. |
| `ansible_requirements_file` | Archivo opcional del repositorio con roles/collections de Galaxy. |
| `source_image` | Nombre opcional de una imagen concreta de `debian-cloud`. |

Ejemplo de argumentos: `["--extra-vars", "@ansible/vars/web.yml"]`; ese archivo debe existir en el repositorio. Para ejecutar varios playbooks, seleccionar un playbook que utilice `import_playbook`, como el ejemplo web existente.

Se puede lanzar desde GitHub CLI, con el workflow ya presente en la rama predeterminada:

```sh
gh workflow run build-image.yml \
  -f playbook=ansible/playbooks/web.yml \
  -f image_family=debian-13-web \
  -f ansible_extra_arguments='[]'
```

La construcción tiene un límite de 75 minutos y el job de 90. Al terminar, descargar el artefacto `image-manifest-...` desde la ejecución. No se realiza una VM de prueba adicional: las comprobaciones incluidas verifican la VM temporal antes de capturar la imagen.
